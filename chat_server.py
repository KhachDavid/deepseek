from flask import Flask, request, jsonify, Response, session, copy_current_request_context, current_app
from flask import render_template
from flask_sqlalchemy import SQLAlchemy

from datetime import datetime, timezone
import datetime
import threading
import ollama
import sys

app = Flask(__name__)
app.secret_key = 'nldsgf4-32io5476in-kjhgfsfd-bkjhbf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_sessions.db'  # SQLite file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the database models: Session and Message
class Session(db.Model):
    __tablename__ = 'sessions'
    session_id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))  # Tememporary solution
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))  # Tem
    messages = db.relationship('Message', backref='session', cascade='all, delete-orphan')

class Message(db.Model):
    __tablename__ = 'messages'
    message_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.session_id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # "user" or "assistant"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(timezone.utc))  # Temporary solution


@app.cli.command('init-db')
def init_db():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
        print("Database initialized!")

# Define the model used for chat
if len(sys.argv) > 1:
    try:
        desiredModel = sys.argv[2]
    except Exception:
        desiredModel = 'deepseek-r1:14b'
else:
    desiredModel = 'deepseek-r1:14b'

# Temporary storage for chat history (per session or global use)
chat_history = []

@app.route('/')
def home():
    return render_template('chat.html')  # Defines the chat interface (frontend)

@app.route('/new_session', methods=['POST'])
def new_session():
    try:
        session_name = request.json.get('session_name', 'Untitled Session')
        new_session = Session(session_name=session_name, created_at=datetime.datetime.now(timezone.utc))

        # Add and commit the session to the database
        db.session.add(new_session)
        db.session.commit()

        # Log the new session ID
        print(f"New session created with ID {new_session.session_id}")
        return jsonify({"session_id": new_session.session_id, "session_name": new_session.session_name})
    except Exception as e:
        print(f"Error creating new session: {e}")
        return jsonify({"error": "Failed to create session"}), 500


@app.route('/sessions', methods=['GET'])
def get_sessions():
    sessions = Session.query.order_by(Session.updated_at.asc()).all()
    return jsonify([
        {"session_id": s.session_id, "session_name": s.session_name, "created_at": s.created_at}
        for s in sessions
    ])

@app.route('/sessions/<int:session_id>', methods=['GET'])
def get_session(session_id):
    try:
        session_obj = Session.query.get(session_id)
        
        if session_obj is None:
            return jsonify({"error": "Session not found"}), 404

        # Return the session data along with its messages
        messages = [
            {"role": message.role, "content": message.content, "created_at": message.created_at}
            for message in session_obj.messages
        ]
        print(f"Retrieved session {session_id} with {len(messages)} messages")
        return jsonify({"session_id": session_obj.session_id, "session_name": session_obj.session_name, "messages": messages})
    except Exception as e:
        print(f"Error retrieving session {session_id}: {e}")
        return jsonify({"error": "Failed to retrieve session"}), 500


@app.route('/delete_session/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    session_to_delete = Session.query.get_or_404(session_id)
    db.session.delete(session_to_delete)
    db.session.commit()
    return jsonify({"message": "Session deleted successfully."})

@app.route('/send', methods=['POST'])
def send():
    """
    Handles user input, sends it to the model, streams the response in chunks,
    and maintains chat context safely using @copy_current_request_context.
    """
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
            print(f"Assistant response saved: {assistant_message}")
        except Exception as e:
            db.session.rollback()  # Rollback any changes on error
            print(f"Error saving chat history: {str(e)}")

    
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

            print(f"\n[{datetime.datetime.now()}] Assistant is responding:\n")
            for chunk in response_iterator:
                token = chunk.get('message', {}).get('content', '')  # Extract the token
                if token:  # Only process non-empty tokens
                    assistant_message += token  # Build the full assistant message
                    print(token, end='', flush=True)  # Print for debugging
                    yield token  # Send the streamed token to the client incrementally

            print("\nAssistant response completed.")
            # Persist the full assistant response into the database
            save_chat_history(assistant_message.strip())

            # Update chat history with assistant response
            chat_history.append({"role": "assistant", "content": assistant_message.strip()})

        except Exception as e:
            error_message = f"[{datetime.datetime.now()}] [ERROR]: {str(e)}"
            print(error_message)  # Log to console
            yield error_message



    # Return a streaming response
    return Response(generate_stream(), content_type='text/plain')

@app.route('/reset', methods=['POST'])
def reset():
    """
    Resets the conversation history to clear the context.
    """
    session.pop('chat_history', None)
    return jsonify({"message": "Chat history reset."})


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
        print(f"Error renaming session {session_id}: {e}")
        db.session.rollback()  # Rollback in case of an error
        return jsonify({"error": "Failed to rename session."}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
