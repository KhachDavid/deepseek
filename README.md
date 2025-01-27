
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=chat_server
flask init-db
nohup python3 chat_server.py deepseek-r1:70b > flask.log 2>&1 &
