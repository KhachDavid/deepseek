from flask import Flask, request, jsonify, render_template
import ollama

app = Flask(__name__)

# Define the model used for chat
desiredModel = 'deepseek-r1:14b'

@app.route('/')
def home():
    return render_template('chat.html')  # Serves the chat frontend

@app.route('/send', methods=['POST'])
def send():
    """Handles user input and sends it to the Ollama model."""
    questionToAsk = request.json.get("message")  # Get user input
    if not questionToAsk:
        return jsonify({"error": "No message provided"}), 400

    try:
        # Use the Ollama API to chat with the model
        response = ollama.chat(
            model='deepseek-r1:14b',
            messages=[
                {
                    'role': 'user',
                    'content': questionToAsk,
                }
            ]
        )
        
        # Extract the model's Markdown-formatted response
        OllamaResponse = response['message']['content']
        return jsonify({"response": OllamaResponse})  # Return it to the frontend
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Start the Flask server
    app.run(host='0.0.0.0', port=8000, debug=True)
