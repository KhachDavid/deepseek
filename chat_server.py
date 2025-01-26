from flask import Flask, request, jsonify, Response, session, copy_current_request_context
from flask import render_template
import threading
import ollama
import sys
import datetime

app = Flask(__name__)
app.secret_key = 'nldsgf4-32io5476in-kjhgfsfd-bkjhbf'

# Define the model used for chat
if len(sys.argv) > 1:
    desiredModel = sys.argv[2]
else:
    desiredModel = 'deepseek-r1:14b'

# Temporary storage for chat history (per session or global use)
chat_history = []

@app.route('/')
def home():
    return render_template('chat.html')  # Defines the chat interface (frontend)

@app.route('/send', methods=['POST'])
def send():
    """
    Handles user input, sends it to the model, streams the response in chunks,
    and maintains chat context safely using @copy_current_request_context.
    """
    if 'chat_history' not in session:
        session['chat_history'] = []

    chat_history = session['chat_history']

    # Get user input from the POST request
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Append the user's message to the conversation history before streaming
    chat_history.append({'role': 'user', 'content': user_message})
    session['chat_history'] = chat_history

    @copy_current_request_context
    def save_chat_history(assistant_message):
        """
        Safely saves the assistant's full response to session chat history after streaming.
        """
        chat_history.append({'role': 'assistant', 'content': assistant_message})
        session['chat_history'] = chat_history  # Save the conversation in the session
    
    def generate_stream():
        """
        Streams the response from the model token by token directly to the client.
        """
        assistant_message = ''  # Collect the assistant's full response
        try:
            # Call the model with streaming enabled
            response_iterator = ollama.chat(model=desiredModel, stream=True, messages=chat_history)
    
            print(f"\n[{datetime.datetime.now()}] Assistant is responding:\n")
            for chunk in response_iterator:
                # Get the content of the message
                token = chunk.get('message', {}).get('content', '')
    
                if token:  # Only handle non-empty tokens
                    # Combine the token into the full assistant message for saving later
                    assistant_message += token
    
                    # Print the token to the console in real-time (helpful for debugging)
                    print(token, end='', flush=True)
    
                    # Yield the token directly to the client
                    yield token  # Send the individual token to the frontend
    
            # Save the assistant's full response to chat history once streaming is done
            threading.Thread(target=save_chat_history, args=(assistant_message.strip(),)).start()
    
        except Exception as e:
            error_message = f"[{datetime.datetime.now()}] [ERROR]: {str(e)}"
            print(f"\n{error_message}")  # Log the error to the console
            yield error_message + "\n"  # Send the error to the client



    # Return the streaming response to the frontend as text/plain
    return Response(generate_stream(), content_type='text/plain')

@app.route('/reset', methods=['POST'])
def reset():
    """
    Resets the conversation history to clear the context.
    """
    session.pop('chat_history', None)
    return jsonify({"message": "Chat history reset."})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
