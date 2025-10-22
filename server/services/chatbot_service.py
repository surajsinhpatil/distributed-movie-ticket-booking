import os
import sys
from openai import OpenAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'protos')))

import protos.chatbot_pb2 as chatbot_pb2
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc
from raft.state_machine import StateMachine

class ChatbotServiceImpl(chatbot_pb2_grpc.ChatbotServiceServicer):
    """Implements the AI-powered chatbot service."""

    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine
        self.openai_client = None
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Simple rule-based intents for fallback
        self.fallback_intents = {
            "cancel": "To cancel a booking, use the `cancel <booking_id>` command.",
            "book": "You can book a seat with `reserve <show_id> <seat_id> <amount>`.",
            "seatmap": "To see available seats, use `seatmap <show_id>`.",
            "help": "Available commands are: login, logout, seatmap, reserve, cancel, listshows, ask, and more.",
            "refund": "Please contact an admin with your payment reference number and they will promptly provide a refund."
        }

    def _get_fallback_answer(self, query):
        """Provides a rule-based answer if LLM is not available or fails."""
        query_lower = query.lower()
        for keyword, answer in self.fallback_intents.items():
            if keyword in query_lower:
                return answer
        return "I'm sorry, I can't answer that question right now. Please try rephrasing."

    def AskQuestion(self, request, context):
        """Answers a user's question using an LLM or fallback intents."""
        session = self.state_machine.get_session(request.session_token)
        if not session:
            context.set_code(401)
            context.set_details("Unauthorized: Invalid session token.")
            return chatbot_pb2.AskQuestionResponse(answer="Please login to use the chatbot.")

        print(f"🤖 Chatbot question from '{session['user_id']}': '{request.query}'")

        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful movie theater assistant. Keep answers concise."},
                        {"role": "user", "content": request.query}
                    ],
                    max_tokens=50
                )
                answer = response.choices[0].message.content.strip()
                print(f"✅ LLM Answer: {answer}")
                return chatbot_pb2.AskQuestionResponse(answer=answer, from_llm=True)
            except Exception as e:
                print(f"⚠️ LLM call failed: {e}. Using fallback.")
                answer = self._get_fallback_answer(request.query)
                return chatbot_pb2.AskQuestionResponse(answer=answer, from_llm=False)
        else:
            # print("🤖 OpenAI API key not set. Using fallback intents.")
            answer = self._get_fallback_answer(request.query)
            return chatbot_pb2.AskQuestionResponse(answer=answer, from_llm=False)
