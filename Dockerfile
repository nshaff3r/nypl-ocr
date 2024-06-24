# Use Miniconda base image
FROM continuumio/miniconda3

# Install system dependencies
RUN apt-get update && apt-get install -y git-all

# Set PATH to include Conda binaries
ENV PATH="/opt/conda/bin:${PATH}"

# Copy environment file and install Conda environment
COPY environment.yml /tmp/environment.yml
RUN conda env create -f /tmp/environment.yml

# Activate the 'ocr' environment
SHELL ["conda", "run", "-n", "ocr", "/bin/bash", "-c"]

# Install additional dependencies in the Conda environment
RUN conda install -n ocr pytorch torchvision torchaudio cpuonly -c pytorch
RUN pip install python-doctr "python-doctr[torch]"
RUN apt-get install -y libpangocairo-1.0-0

# Clone the repository
RUN git clone https://github.com/nshaff3r/nypl-ocr.git /nypl-ocr

# Set the working directory to the cloned repository
WORKDIR /nypl-ocr

# Copy the rest of your files into the container
COPY . .

# Uninstall opencv-python and opencv-python-headless (if they exist)
RUN pip uninstall -y opencv-python opencv-python-headless || true

# Reinstall opencv-python-headless
RUN pip install opencv-python-headless
RUN pip install joblib

# Set the entry point to run your application and display the installed packages
CMD ["conda", "run", "-n", "ocr", "/bin/bash", "-c", "python ./benchmark.py"]

