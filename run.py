from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from joblib import Parallel, delayed
import json
import queue
import torch
import imutils
import random
from time import sleep
import itertools
import json
import cv2
import fcntl
import uuid
import threading
import queue
import sys
import dotenv, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from convertToGreyscale import pdf_process


SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.metadata.readonly"]

# Global queues
download_queue = queue.Queue()  # Limit number of downloads in queue

model = ocr_predictor(det_arch="linknet_resnet18", reco_arch="crnn_mobilenet_v3_small", assume_straight_pages=True, det_bs=2048, reco_bs=2048, pretrained=True)

model.det_predictor.model.postprocessor.bin_thresh = 0.002
model.det_predictor.model.postprocessor.box_thresh = 0.002

download_counter = 0
pdf_counter = 0

print_lock = threading.Lock()
counter_lock = threading.Lock()

tasks = os.cpu_count() - 3

def append_json_safely(filename, data, imgname=""):
    json_output = data
    unique_separator = "\n"
    if len(imgname) > 0: 
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

def safe_print(*args, file=sys.stdout, **kwargs):
    with print_lock:
        print(*args, file=file, **kwargs)
    

def download_file(file_id, destination_path, drive_service):
    request = drive_service.files().get_media(fileId=file_id)
    
    with open(destination_path, 'wb') as file:
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    return status.progress()

def downloader_worker(folder_id, drive_service):
    global download_counter
    page_token = None
    while True:
        response = drive_service.files().list(
            q=f"'{folder_id}' in parents",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=page_token
        ).execute()
        
        for file in response.get('files', []):
            safe_print(f"Downloading {file['name']}")
            file_path = os.path.join("downloads", file['name'])
            status = download_file(file['id'], file_path, drive_service)
            if status != 1.0:
                safe_print(f"ERROR: issue downloading {file['name']}")
            else:
                with counter_lock:
                    download_counter += 1
                    safe_print(f"Downloaded {download_counter} files")

            download_queue.put((file_path, file['name']))
        
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    download_queue.put(None)
    safe_print(f"Download completed. Total files downloaded: {download_counter}")

def processor_worker():
    global pdf_counter, tasks
    while True:
        item = download_queue.get()
        if item is None:
            safe_print(f"PDF processing completed. Total PDFs processed: {pdf_counter}")
            break
        pdf_path, pdf_name = item
        output_dir = f"splitpdfs"
        # Process the PDF and generate images
        pdf_process(pdf_path, output_dir, pdf_name, tasks)

        with counter_lock:
            pdf_counter += 1
            safe_print(f"Processed PDF {pdf_counter}: {pdf_name}")

        download_queue.task_done()

# OCR PIPELINE :)
def worker(directory):
   processed = []
   while True:
        images = os.listdir(directory)
        images = list(set(images) - set(processed))
        while len(images) == 0:
            sleep(1)
            images = os.listdir(directory)
        image_path = images[0]
        processed.append(image_path)
        image_path = os.path.join(directory, image_path)
        # Perform OCR
        doc = DocumentFile.from_images(image_path)
        with torch.no_grad():
            res = model(doc)

            # checks for valid rotation
            line = [block["lines"][0]["words"] for block in res.export()["pages"][0]["blocks"]]
            confidences = [word["confidence"] > .5 for block in line for word in block]
            if len(confidences) == 0:
                append_json_safely("unread.txt", f"{image_path}\tno data")
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
                        append_json_safely("unread.txt", f"{image_path}\tunreadable")
                        continue
                    if new_validity > validity:
                        res = new_res
                        validity = new_validity
                if res is not None:
                    append_json_safely("read.txt", image_path)
                    append_json_safely("ocr-data.json", res.export(), imgname=image_path)
                else:
                    append_json_safely("unread.txt", f"{image_path}\tocr error")
                

def process_drive_folder(folder_id, drive_service):
    global tasks
    directories = []
    for i in range(tasks):
        os.makedirs(f"splitpdfs{i + 1}")
        directories.append(f"splitpdfs{i + 1}")
    # Start the downloader in a separate thread
    downloader_thread = threading.Thread(target=downloader_worker, args=(folder_id, drive_service))
    downloader_thread.start()

    # Start the PDF processor
    pdf_processor = threading.Thread(target=processor_worker)
    pdf_processor.start()

    Parallel(n_jobs=-4)(delayed(worker)(directory) for directory in directories)

    # Wait for all threads to complete
    downloader_thread.join()
    pdf_processor.join()


    download_queue.join()
    print("download queue joined")

    read_count = sum(1 for _ in open('read.txt'))
    unread_count = sum(1 for _ in open('unread.txt'))
    safe_print(f"Total files downloaded: {download_counter}")
    safe_print(f"Total PDFs processed: {pdf_counter}")
    safe_print(f"Total readable images: {read_count}")
    safe_print(f"Total unreadable images: {unread_count}")


if __name__ == "__main__":
    dotenv.load_dotenv(".env", override=True)
    os.environ["USE_TORCH"] = "1"

    print('USE_TORCH = ', os.environ.get('USE_TORCH'))

    print("setup complete")

    # Initialize the Google Drive API client
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)

    folder_id = '1lLkumnjgnRCi21snefoheQpypzTnujQn'
    process_drive_folder(folder_id, drive_service)

    print("All processing complete.")
