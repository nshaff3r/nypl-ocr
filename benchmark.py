
from doctr.io import DocumentFile
from datetime import datetime
from doctr.models import ocr_predictor
import json
import multiprocessing as mp
from joblib import Parallel, delayed
import os, sys

NUM_CORES = 8

model = ocr_predictor(det_arch="linknet_resnet18", pretrained=True)
print(mp.current_process(),end='\n\n')

def worker(file_name):
    print(file_name)
    doc = DocumentFile.from_pdf(file_name)
    return model(doc)

def mp_handler(tasks):
    p = mp.Pool(NUM_CORES)
    p.map(worker, tasks)


# if __name__ == "__main__":
startTime = datetime.now()
tasks = []
folder = "pdfs/split_pages/"
for i, name in enumerate(os.listdir(folder)):
    file_path = "original/split_pages/" + name
    tasks.append(file_path)
print("setup complete")

#     mp_handler(tasks)


results = Parallel(n_jobs=-1)(delayed(worker)(x) for x in tasks)
print(datetime.now() - startTime)