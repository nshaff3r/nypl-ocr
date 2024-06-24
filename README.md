# nypl-ocr
Pipeline for running OCR on digitized catalog cards.

Because of all the libraries required, the install process can be simplified with the Docker container
(note that the container has only been verified to work on Linux Debian). Simply run 
```docker build -t ocr .```
and 
```docker run ocr```

If you're not using Docker, you can install according to requirements.txt and 
follow the instructions on [doctr](https://mindee.github.io/doctr/getting_started/installing.html)
and then  ```python3 benchmark.py```.