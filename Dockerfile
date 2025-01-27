# Use an official lightweight Python image as a base
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's cache
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV FLASK_APP=chat_server
ENV FLASK_ENV=production

# Expose the port the app runs on
EXPOSE 8000

# Command to run when the container launches
# nohup python3 chat_server.py deepseek-r1:70b > flask.log 2>&1 &
CMD ["nohup", "python3", "chat_server.py", "deepseek-r1:70b", ">", "flask.log", "2>&1", "&"]