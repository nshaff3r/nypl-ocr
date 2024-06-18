
from doctr.io import DocumentFile
from datetime import datetime
from doctr.models import ocr_predictor
from joblib import Parallel, delayed
import os

model = ocr_predictor(det_arch="linknet_resnet18", pretrained=True)

def worker(file_name):
    print(f"{progress[file_name]}: {file_name}")
    doc = DocumentFile.from_pdf(file_name)
    return model(doc)

progress = {}
tasks = []
folder = "pdfs/split_pages/"
for i, name in enumerate(os.listdir(folder)):
    if "pdf" in name:
        file_path = "pdfs/split_pages/" + name
        tasks.append(file_path)
        progress[file_path] = i
print("setup complete",end='\n\n')

startTime = datetime.now()
results = Parallel(n_jobs=-1)(delayed(worker)(x) for x in tasks)
print("Benchmarked time: " + str(datetime.now() - startTime))