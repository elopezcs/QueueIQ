# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project's code into the container
COPY . .

EXPOSE 8501

# Command to run your application (adjust 'main.py' to your entry point)
CMD ["streamlit", "run", "queue-simulation/frontend-dashboard.py"]