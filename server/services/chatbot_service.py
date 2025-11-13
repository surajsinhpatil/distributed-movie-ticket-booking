import os
import sys

# --- Fix this block ---
# Add project root to sys.path for cross-platform module imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# --- End block ---

import protos.chatbot_pb2 as chatbot_pb2
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()

class ChatbotServiceImpl(chatbot_pb2_grpc.ChatbotServiceServicer):
    """Implements the chatbot service."""

    def __init__(self, state_machine):
        self.state_machine = state_machine # Store it even if not currently used heavily
        self.openai_client = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                self.openai_client = OpenAI()
                print("🤖 OpenAI client initialized.")
            except Exception as e:
                print(f"⚠️  Warning: Failed to initialize OpenAI client: {e}")
                print("Chatbot will only use fallback answers.")
        else:
            print("🤖 No OPENAI_API_KEY found. Chatbot will only use fallback answers.")
            
        # Hardcoded fallback intents for common questions
        self.fallback_intents = {
            "cancel": "To cancel a booking, use the `cancel <booking_id>` command. You can find your booking ID from your confirmation.",
            "book": "You can book a seat using the `reserve <show_id> <amount> <seat_ids...>` command. First, use `listshows` to see show IDs and `seatmap <show_id>` to see available seats.",
            "refund": "Refunds are processed by admins. If you cancel a booking, a refund is processed automatically. For other issues, please contact support.",
            "help": "You can type `help` in the main client to see all available commands.",
            "login": "Use the `login <username> <password>` command to log in. The default user is 'alice' with password 'secret'."
        }

    def _get_fallback_answer(self, query):
        """Checks for a hardcoded fallback answer."""
        query_lower = query.lower()
        for keyword, answer in self.fallback_intents.items():
            if keyword in query_lower:
                return answer
        return None

    def _get_llm_answer(self, query):
        """Gets an answer from the OpenAI LLM."""
        if not self.openai_client:
            return None
            
        try:
            completion = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for a movie ticket booking system. Be concise and friendly."},
                    {"role": "user", "content": query}
                ],
                max_tokens=100
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"❌ Error calling OpenAI: {e}")
            return None

    def AskQuestion(self, request, context):
        """Answers a user's question, using fallback or LLM."""
        print(f"🤖 Received question: '{request.query}'")
        
        # 1. Try to find a fallback answer first
        answer = self._get_fallback_answer(request.query)
        from_llm = False
        
        # 2. If no fallback, try the LLM
        if not answer:
            answer = self._get_llm_answer(request.query)
            from_llm = True

        # 3. If LLM fails or is disabled, use a generic response
        if not answer:
            answer = "I'm sorry, I don't have an answer for that right now."
            from_llm = False
            
        print(f"🤖 Sending answer (from_llm={from_llm}): {answer[:50]}...")
        return chatbot_pb2.AskQuestionResponse(answer=answer, from_llm=from_llm)