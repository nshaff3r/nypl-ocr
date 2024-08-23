from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from joblib import Parallel, delayed
import json
import queue
import torch
import imutils
import itertools
import json
import cv2
import fcntl
import uuid
import threading
import queue
import dotenv, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from convertToGreyscale import pdf_process


def append_json_safely(filename, data, imgname):
    # Add the filename to the data
    data_with_filename = data.copy()  # Create a copy to avoid modifying the original data
    data_with_filename['filename'] = imgname
    
    json_output = json.dumps(data_with_filename)
    unique_separator = f"\n<<<{uuid.uuid4()}>>\n"
    
    with open(filename, "a") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            file.write(unique_separator)
            file.write(json_output)
            file.flush()
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)

def download_file(file_id, destination_path):
    request = drive_service.files().get_media(fileId=file_id)
    
    with open(destination_path, 'wb') as file:
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    return status.progress()

def downloader_worker(folder_id):
    page_token = None
    while True:
        response = drive_service.files().list(
            q=f"'{folder_id}' in parents",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=page_token
        ).execute()
        
        for file in response.get('files', []):
            print("DOWNLOADING: {}".format(file['name']))
            file_path = os.path.join("downloads", file['name'])
            status = download_file(file['id'], file_path)
            if status != 1.0:
                print("ERROR: {}".format(file['name']))
            download_queue.put((file_path, file['name']))
        
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    
    # Signal that all files have been downloaded
    download_queue.put(None)

def processor_worker():
    while True:
        item = download_queue.get()
        if item is None:
            process_queue.put(None)  # Propagate the stop signal
            print("DONEEEE: {}".format(download_queue.qsize()))
            break
        pdf_path, pdf_name = item

        output_dir = "splitpdfs"
        # Process the PDF and generate images
        pdf_process(pdf_path, output_dir, pdf_name)
        
        # Queue processed images for OCR
        for img_name in sorted(os.listdir(output_dir)):
            img_path = os.path.join(output_dir, img_name)
            process_queue.put(img_path)

        download_queue.task_done()

# OCR PIPELINE :)
def worker():
   unreadable = []
   readable = []
   while True:
        try:
            image_path = process_queue.get(timeout=5)  # 1 second timeout
        except queue.Empty:
            continue

        if image_path is None:
            print("EMPTY QUEUE")
            break

        # Perform OCR
        print("Size: {}".format(process_queue.qsize()))
        doc = DocumentFile.from_images(image_path)
        with torch.no_grad():
            res = model(doc)

            # checks for valid rotation
            line = [block["lines"][0]["words"] for block in res.export()["pages"][0]["blocks"]]
            confidences = [word["confidence"] > .5 for block in line for word in block]
            if len(confidences) == 0:
                print("Error: no data in {}".format(image_path))
                unreadable.append(image_path)
            else:
                validity = sum(confidences) / len(confidences)
                if validity < .85:
                    rotated = (imutils.rotate(cv2.imread(image_path), angle=180))
                    cv2.imwrite(image_path, rotated)
                    doc = DocumentFile.from_images(image_path)
                    new_res = model(doc)
                    line = [block["lines"][0]["words"] for block in new_res.export()["pages"][0]["blocks"]]
                    confidences = [word["confidence"] > .5 for block in line for word in block]
                    new_validity = sum(confidences) / len(confidences)
                    if new_validity < .85:
                        unreadable.append(image_path)
                    if new_validity > validity:
                        res = new_res
                        validity = new_validity
                length = len(readable) + len(unreadable)
                if res is not None:
                    readable.append(image_path)
                    append_json_safely("ocr-data.json", res.export(), image_path)
                    print("{} Finished {}".format(length + 1, image_path))
                else:
                    unreadable.append(image_path)
                    print("{} Issue with {}".format(length + 1, image_path))
            os.unlink(image_path)
            process_queue.task_done()
            return (unreadable, readable)

def process_drive_folder(folder_id):
    # Start the downloader in a separate thread
    downloader_thread = threading.Thread(target=downloader_worker, args=(folder_id,))
    downloader_thread.start()

    # Start the PDF processor
    pdf_processor = threading.Thread(target=processor_worker)
    pdf_processor.start()

    # Use joblib to parallelize OCR
    results = Parallel(n_jobs=-2, backend="threading")(delayed(worker)() for _ in itertools.count())

    # Wait for all threads to complete
    downloader_thread.join()
    pdf_processor.join()


    download_queue.join()
    print("download queue joined")
    process_queue.join()
    print("process queue joined")

    # Combine results
    all_unreadable = []
    all_readable = []
    for unreadable, readable in results:
        all_unreadable.extend(unreadable)
        all_readable.extend(readable)

    print(f"Total processed: {len(all_readable)}")
    print(f"Total unreadable: {len(all_unreadable)}")

    return all_unreadable, all_readable



SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]

dotenv.load_dotenv(".env", override=True)
os.environ["USE_TORCH"] = "1"

print('USE_TORCH = ', os.environ.get('USE_TORCH'))


model = ocr_predictor(det_arch="linknet_resnet18", reco_arch="crnn_mobilenet_v3_small", assume_straight_pages=True, det_bs=2048, reco_bs=2048, pretrained=True)

model.det_predictor.model.postprocessor.bin_thresh = 0.002
model.det_predictor.model.postprocessor.box_thresh = 0.002

print("setup complete")

# Initialize the Google Drive API client
creds = Credentials.from_authorized_user_file('token.json', SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# Global queues
download_queue = queue.Queue()  # Limit number of downloads in queue
process_queue = queue.Queue()  # Limit number of processed images in queue

folder_id = '1lLkumnjgnRCi21snefoheQpypzTnujQn'
process_drive_folder(folder_id)

print("All processing complete :)")
