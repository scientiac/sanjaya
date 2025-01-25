from flask import Flask, render_template, jsonify
import threading
import RPi.GPIO as GPIO
import time
import google.generativeai as genai

# Configure the Gemini API
api_key = 'AIzaSyC--UqC2V3iwTjSxRsRVfNB_k-kuM8MYTg'  # Replace with your actual API key
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro')

# Define the Morse code dictionary
morse_dict = {
    '.-': 'a', '-...': 'b', '-.-.': 'c', '-..': 'd', '.': 'e', '..-.': 'f', '--.': 'g', '....': 'h', '..': 'i',
    '.---': 'j', '-.-': 'k', '.-..': 'l', '--': 'm', '-.': 'n', '---': 'o', '.--.': 'p', '--.-': 'q', '.-.': 'r',
    '...': 's', '-': 't', '..-': 'u', '...-': 'v', '.--': 'w', '-..-': 'x', '-.--': 'y', '--..': 'z',
    '-----': '0', '.----': '1', '..---': '2', '...--': '3', '....-': '4', '.....': '5', '-....': '6', '--...': '7',
    '---..': '8', '----.': '9', '.-.-': 'redo', '..--': 'save', '---.': 'clean',
}

# Set up the GPIO pin
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Flask app setup
app = Flask(__name__)

# Shared state for Morse code and decoded messages
state = {
    "morse_code": "",
    "decoded_message": "",
    "decoded_single": "",
    "suggestions": [],
    "word_selection_list": [],
    "selection_mode": False,
    "highlighted_index": 0,
    "generated_sentence": "",
    "saved_sentences": [],
}

def get_word_suggestions(prefix):
    """Fetch word suggestions based on the prefix and previously selected words."""
    try:
        # Include the context of previously selected words in the prompt
        context = " ".join(state["word_selection_list"]) if state["word_selection_list"] else ""

        prompt = (
            f"Generate 5 different simple English words starting with '{prefix}'. "
            f"Words must start with the '{prefix}' and be closely related to the context: '{context}'. "
            f"Words must be common everyday English words only and if not then only special words. "
            f"Respond with ONLY the words in English, separated by commas."
            f"Example format: word1, word2, word3, word4, word5"
        )
        
        response = model.generate_content(prompt)
        if hasattr(response, 'text') and response.text:
            words = [word.strip() for word in response.text.split(',') if word.strip()]
            return words[:5]
    except Exception as e:
        print(f"Error fetching suggestions: {e}")
    return []

def generate_minimal_sentence(word_list):
    """
    Generate a minimal sentence using the Gemini API based on selected words.
    """
    try:
        # Prepare context from previously selected words
        context = " ".join(word_list) if word_list else ""
        
        # Construct a precise prompt for minimal sentence generation
        prompt = (
            f"Generate a single, simple, and short sentence using these words: {', '.join(word_list)}. "
            f"Context of previous words: '{context}'. "
            f"Ensure the sentence is grammatically correct, concise, and uses all or most of the given words. "
            f"The sentence should be no more than 10 words long and suitable for everyday communication. "
            f"Respond with ONLY the sentence and the sentence should be the SIMPLEST making sense sentence to understand the given context only and not anything else not even additional adjectives should be added."
        )
        
        response = model.generate_content(prompt)
        if hasattr(response, 'text') and response.text:
            # Clean and trim the generated sentence
            return response.text.strip()
    except Exception as e:
        print(f"Error generating sentence: {e}")
    return ""

def detect_morse():
    morse_code = ''
    start_time = None
    last_signal = None
    last_time = 0

    while True:
        if GPIO.input(17) == GPIO.LOW:  # Button pressed
            if start_time is None:
                start_time = time.time()

            while GPIO.input(17) == GPIO.LOW:  # Wait for release
                pass

            press_duration = time.time() - start_time
            start_time = None

            current_time = time.time()

            if state["selection_mode"]:  # Handle selection mode
                if press_duration >= 0.5:  # Long press: Select the highlighted suggestion
                    if state["suggestions"]:
                        selected_word = state["suggestions"][state["highlighted_index"]]
                        state["word_selection_list"].append(selected_word)
                        if len(state["word_selection_list"]) >= 2:
                            state["generated_sentence"] = generate_minimal_sentence(state["word_selection_list"])
        
                        state["selection_mode"] = False
                        state["highlighted_index"] = 0
                        state["decoded_message"] = ""
                        state["suggestions"] = []
                else:  # Short press: Cycle through suggestions
                    if state["suggestions"]:
                        state["highlighted_index"] = (state["highlighted_index"] + 1) % len(state["suggestions"])
            else:  # Handle input mode
                if press_duration >= 5:  # Long press: Enter selection mode
                    state["selection_mode"] = True
                    state["highlighted_index"] = 0
                elif press_duration >= 0.5:  # Dash (0.5 seconds or more)
                    morse_code += '-'
                    last_signal = '-'
                    last_time = current_time
                else:  # Dot (less than 0.5 seconds)
                    if (last_signal != '.' and last_signal != '-') or (current_time - last_time >= 0.2):
                        morse_code += '.'
                        last_signal = '.'
                        last_time = current_time

                # Update shared state for the web UI
                state["morse_code"] = morse_code
        elif GPIO.input(17) == GPIO.HIGH:  # Button released
            if start_time is None:
                idle_time = 0
                while GPIO.input(17) == GPIO.HIGH:  # Detect idle time
                    time.sleep(0.1)
                    idle_time += 0.1
                    if idle_time >= 2:  # No activity for 2 seconds
                        if morse_code:
                            if morse_code in morse_dict:
                                decoded_char = morse_dict[morse_code]
                                if decoded_char == 'save':
                                    # Check if a generated sentence exists before saving
                                    if state["generated_sentence"]:
                                        # Save the current sentence
                                        state["saved_sentences"].append(state["generated_sentence"])
                                        
                                        # Limit saved sentences to the last 10
                                        state["saved_sentences"] = state["saved_sentences"][-10:]
                                        
                                        # Reset state variables to prepare for next sentence input
                                        state["generated_sentence"] = ""  # Clear generated sentence
                                        state["word_selection_list"] = []  # Clear selected words list
                                        state["decoded_message"] = ""  # Clear decoded message
                                        state["suggestions"] = []  # Clear suggestions
                                        state["morse_code"] = ""  # Clear current Morse code input
                                        state["decoded_single"] = ""  # Clear last decoded character
                                elif decoded_char == 'clean':
                                    state["generated_sentence"] = ""  # Clear generated sentence
                                    state["word_selection_list"] = []  # Clear selected words list
                                    state["decoded_message"] = ""  # Clear decoded message
                                    state["suggestions"] = []  # Clear suggestions
                                    state["morse_code"] = ""  # Clear current Morse code input
                                    state["decoded_single"] = ""  # Clear last decoded character
                                elif decoded_char == 'redo':
                                    state["decoded_message"] = ''
                                    state["suggestions"] = []
                                else:
                                    state["decoded_message"] += decoded_char
                                    state["decoded_single"] = decoded_char
                                    # Generate suggestions after a letter is added
                                    state["suggestions"] = get_word_suggestions(state["decoded_message"])
                            else:
                                state["decoded_single"] = ''
                        morse_code = ''
                        state["morse_code"] = morse_code
                        break

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_state')
def get_state():
    return jsonify(state)

# Run the Morse code detection in a separate thread
def start_morse_thread():
    thread = threading.Thread(target=detect_morse, daemon=True)
    thread.start()

if __name__ == '__main__':
    start_morse_thread()
    app.run(host='0.0.0.0', port=5000)
