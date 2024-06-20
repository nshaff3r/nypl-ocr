
from doctr.io import DocumentFile
from datetime import datetime
from doctr.models import ocr_predictor
from joblib import Parallel, delayed
import torch
import joblib
import os

print(f"There are {joblib.cpu_count()} cores.")
model = ocr_predictor(det_arch="linknet_resnet18", reco_arch="crnn_mobilenet_v3_small", det_bs=2048, reco_bs=2048, pretrained=True)

def worker(file_name):
    print(f"{progress[file_name]}: {file_name}")
    doc = DocumentFile.from_images(file_name)
    with torch.no_grad():
        return model(doc)

progress = {}
tasks = []
results = []
folder = "pdfs/split_pages/"
for i, name in enumerate(os.listdir(folder)):
    if "jpeg" in name:
        file_path = "pdfs/split_pages/" + name
        tasks.append(file_path)
        progress[file_path] = i

print("setup complete",end='\n\n')

startTime = datetime.now()
results = Parallel(n_jobs=-1)(delayed(worker)(x) for x in tasks)
print("Benchmarked time: " + str(datetime.now() - startTime))