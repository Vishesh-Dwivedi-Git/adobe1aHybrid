# Use a specific, stable version of Python on a slim base image.
# Explicitly set the platform to linux/amd64 for compatibility as required.
FROM --platform=linux/amd64 python:3.9-slim

# Set the working directory inside the container.
# All subsequent commands will run from this directory.
WORKDIR /app

# Copy the dependencies file first.
# This leverages Docker's layer caching. The dependencies will only be re-installed
# if the requirements.txt file changes.
COPY requirements.txt .

# Install the Python dependencies specified in requirements.txt.
# --no-cache-dir reduces the image size by not storing the cache.
# --trusted-host is used to avoid SSL issues with the Python package index.
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the entire 'src' directory into the container at the current working directory (/app).
# This contains all the Python source code for the extractor.
COPY ./src .

# Specify the command to run when the container starts.
# This executes the main.py script, which will process the PDFs
# from the mounted /app/input directory and write JSON to /app/output.
CMD ["python", "main.py"]
