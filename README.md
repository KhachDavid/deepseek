# Running DeepSeek-R1 Locally

Running DeepSeek-R1 locally requires the installation of Ollama and the DeepSeek-R1 model. The server can be run using Flask. The following instructions will guide you through the installation and running of the server.

## Installation

Install Ollama:
```
curl -fsSL https://ollama.com/install.sh | sh
```

Install the DeepSeek-R1 model:
```
ollama run deepseek-r1:14b
```

Use one of:
```
deepseek-r1:1.5b: 1.1 GB (Good for testing and resource-constrained systems)
deepseek-r1:7b: 4.7 GB
deepseek-r1:8b: 4.9 GB
deepseek-r1:14b: 9 GB (Recommended for a balance of performance and resource usage)
deepseek-r1:32b: 19 GB (Use with caution; requires significant RAM)
deepseek-r1:70b: 42 GB (Requires substantial disk space and powerful hardware)
deepseek-r1:671b: 404 GB (Not practical for most personal computers)
```

Create a virtual environment:
```
python3 -m venv venv
```

Activate the virtual environment:
```
source venv/bin/activate
```

Install the requirements:
```
pip install -r requirements.txt
```

## Running the Server

Export the Flask app:
```
export FLASK_APP=chat_server
```

Run the server:
```
flask init-db
```

Keep the server running:
```
nohup python3 chat_server.py deepseek-r1:70b > flask.log 2>&1 &
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
