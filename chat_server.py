from flask import Flask, request, jsonify, Response, session as login_session, copy_current_request_context
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash  # Secure password handling
from datetime import datetime, timezone
import datetime
import ollama
import sys

app = Flask(__name__)
app.secret_key = 'nldsgf4-32io5476in-kjhgfsfd-bkjhbf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_sessions.db'  # SQLite file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

if len(sys.argv) > 1:
    try:
        desiredModel = sys.argv[1]
    except Exception:
        desiredModel = 'deepseek-r1:14b'
else:
    desiredModel = 'deepseek-r1:14b'

# Define the database models: User, Session, and Message
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hashed password
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    sessions = db.relationship('Session', backref='user', cascade='all, delete-orphan')  # User's sessions


class Session(db.Model):
    __tablename__ = 'sessions'
    session_id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)  # Link to user
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))
    messages = db.relationship('Message', backref='session', cascade='all, delete-orphan')


class Message(db.Model):
    __tablename__ = 'messages'
    message_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.session_id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # "user" or "assistant"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))


@app.cli.command('init-db')
def init_db():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
        print("Database initialized!")


# Temporary storage for chat history (per session or global use)
chat_history = []


# Authentication Routes

@app.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    """
    username = request.json.get('username')
    password = request.json.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Check if the username is already taken
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"error": "Username is already taken"}), 400

    # Create a new user with hashed password
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully!"})


@app.route('/login', methods=['POST'])
def login():
    """
    Log in the user and create a session.
    """
    username = request.json.get('username')
    password = request.json.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Verify the user exists and the password is correct
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        # Store user info in the session
        login_session['user_id'] = user.user_id
        login_session['username'] = user.username
        return jsonify({"message": "Login successful!", "user_id": user.user_id})

    return jsonify({"error": "Invalid username or password"}), 401


@app.route('/logout', methods=['POST'])
def logout():
    """
    Log out the user and clear the session.
    """
    login_session.clear()
    return jsonify({"message": "Logout successful!"})

@app.route('/user_status', methods=['GET'])
def user_status():
    """
    Check whether the user is logged in.
    Returns the user's status and username if logged in.
    """
    if 'user_id' in login_session:
        # User is logged in — return their status and username
        return jsonify({
            "logged_in": True,
            "username": login_session['username']
        })
    
    # User is not logged in
    return jsonify({"logged_in": False})


# Helper function to get the current logged-in user
def get_current_user():
    if 'user_id' in login_session:
        return User.query.get(login_session['user_id'])
    return None


# Chat Session Routes

@app.route('/')
def home():
    return render_template('chat.html')  # Defines the chat interface (frontend)


@app.route('/new_session', methods=['POST'])
def new_session():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        session_name = request.json.get('session_name', 'Untitled Session')
        new_session = Session(session_name=session_name, user_id=user.user_id)
        db.session.add(new_session)
        db.session.commit()

        return jsonify({"session_id": new_session.session_id, "session_name": new_session.session_name})
    except Exception as e:
        return jsonify({"error": "Failed to create session"}), 500


@app.route('/sessions', methods=['GET'])
def get_sessions():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    # Fetch only the sessions belonging to the logged-in user
    sessions = Session.query.filter_by(user_id=user.user_id).order_by(Session.updated_at.asc()).all()
    return jsonify([
        {"session_id": s.session_id, "session_name": s.session_name, "created_at": s.created_at}
        for s in sessions
    ])


@app.route('/sessions/<int:session_id>', methods=['GET'])
def get_session(session_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    session_obj = Session.query.filter_by(session_id=session_id, user_id=user.user_id).first()
    if session_obj is None:
        return jsonify({"error": "Session not found"}), 404

    # Return the session data along with its messages
    messages = [
        {"role": message.role, "content": message.content, "created_at": message.created_at}
        for message in session_obj.messages
    ]
    return jsonify({"session_id": session_obj.session_id, "session_name": session_obj.session_name, "messages": messages})


@app.route('/delete_session/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    session_to_delete = Session.query.filter_by(session_id=session_id, user_id=user.user_id).first()
    if session_to_delete is None:
        return jsonify({"error": "Session not found"}), 404

    db.session.delete(session_to_delete)
    db.session.commit()
    return jsonify({"message": "Session deleted successfully."})


# Send Message Route (unchanged except for session/user verification)
@app.route('/send', methods=['POST'])
def send():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    session_id = request.json.get('session_id')
    user_message = request.json.get('message')

    if session_id is None or user_message is None:
        return jsonify({"error": "Session ID and message are required"}), 400

    # Verify the session exists
    session_obj = Session.query.get(session_id)
    if session_obj is None:
        return jsonify({"error": "Session not found"}), 404

    # Retrieve the chat history for the session
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in session_obj.messages
    ]

    # Append the user's message as the next entry
    new_message = Message(session_id=session_id, role="user", content=user_message)
    db.session.add(new_message)
    db.session.commit()
    
    @copy_current_request_context
    def save_chat_history(assistant_message):
        """
        Safely saves the assistant's full response to session chat history.
        """
        try:
            # Save the assistant's message to the database
            new_response = Message(session_id=session_id, role='assistant', content=assistant_message)
            db.session.add(new_response)
            db.session.commit()
        except Exception as e:
            db.session.rollback()  # Rollback any changes on error

    
    def generate_stream():
        """
        Streams the response from the model token-by-token directly to the client.
        """
        nonlocal chat_history  # Allow local modification of chat_history
        assistant_message = ''  # To accumulate the assistant's response

        # Update chat history with the user's latest message
        chat_history.append({"role": "user", "content": user_message})

        try:
            # Call the model with streaming enabled
            response_iterator = ollama.chat(model=desiredModel, stream=True, messages=chat_history)

            for chunk in response_iterator:
                token = chunk.get('message', {}).get('content', '')  # Extract the token
                if token:  # Only process non-empty tokens
                    assistant_message += token  # Build the full assistant message
                    yield token  # Send the streamed token to the client incrementally

            # Persist the full assistant response into the database
            save_chat_history(assistant_message.strip())

            # Update chat history with assistant response
            chat_history.append({"role": "assistant", "content": assistant_message.strip()})

        except Exception as e:
            error_message = f"[{datetime.datetime.now()}] [ERROR]: {str(e)}"
            yield error_message

    # Return a streaming response
    return Response(generate_stream(), content_type='text/plain')

@app.route('/rename_session/<int:session_id>', methods=['PUT'])
def rename_session(session_id):
    """
    Updates the name of the session specified by the session_id.
    """
    try:
        # Fetch the new session name from the request JSON body
        new_session_name = request.json.get('session_name')

        # Validate the new session name
        if not new_session_name or new_session_name.strip() == "":
            return jsonify({"error": "Session name cannot be empty."}), 400

        # Find the session by ID
        session_obj = Session.query.get(session_id)
        if session_obj is None:
            return jsonify({"error": "Session not found."}), 404

        # Update the session name and the updated_at timestamp
        session_obj.session_name = new_session_name.strip()
        session_obj.updated_at = datetime.datetime.now(timezone.utc)

        # Commit the changes to the database
        db.session.commit()

        return jsonify({
            "message": "Session renamed successfully.",
            "session_id": session_obj.session_id,
            "session_name": session_obj.session_name
        })
    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return jsonify({"error": "Failed to rename session."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
