FROM python:3.10-slim

# Set the working directory

WORKDIR /app

# Copy the current directory contents into the container at /app
COPY main.py /app
COPY req.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r req.txt

# Run main.py when the container launches
CMD ["python", "main.py"]