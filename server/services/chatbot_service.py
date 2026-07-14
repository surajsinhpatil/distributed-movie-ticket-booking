import logging
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import protos.chatbot_pb2 as chatbot_pb2
import protos.chatbot_pb2_grpc as chatbot_pb2_grpc
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables (notably OPENAI_API_KEY) if a .env file exists.
load_dotenv()

logger = logging.getLogger(__name__)


class ChatbotServiceImpl(chatbot_pb2_grpc.ChatbotServiceServicer):
    """Customer-support chatbot with rule-based fallback and optional LLM."""

    def __init__(self, state_machine):
        self.state_machine = state_machine
        self.openai_client = None

        if os.getenv("OPENAI_API_KEY"):
            try:
                self.openai_client = OpenAI()
                logger.info("OpenAI client initialized.")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to initialize OpenAI client: %s", exc)
                logger.warning("Chatbot will use fallback answers only.")
        else:
            logger.info("No OPENAI_API_KEY set; chatbot will use fallback answers only.")

        # Rule-based answers for common questions when the LLM is unavailable.
        self.fallback_intents = {
            "cancel": "To cancel a booking, use `cancel <booking_id>`. You can find your booking ID on your confirmation.",
            "book": "To book, use `reserve <show_id> <amount> <seat_ids...>`. Use `listshows` for show IDs and `seatmap <show_id>` for availability.",
            "refund": "Cancelling a booking refunds it automatically. For other issues, please contact an admin.",
            "help": "Type `help` in the client to see all available commands.",
            "login": "Use `login <username> <password>` to log in.",
        }

    def _get_fallback_answer(self, query):
        query_lower = query.lower()
        for keyword, answer in self.fallback_intents.items():
            if keyword in query_lower:
                return answer
        return None

    def _get_llm_answer(self, query):
        if not self.openai_client:
            return None
        try:
            completion = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant for a movie ticket booking system. Be concise and friendly.",
                    },
                    {"role": "user", "content": query},
                ],
                max_tokens=100,
            )
            return completion.choices[0].message.content
        except Exception as exc:
            logger.error("Error calling OpenAI: %s", exc)
            return None

    def AskQuestion(self, request, context):
        logger.info("Chatbot question: %s", request.query)

        answer = self._get_fallback_answer(request.query)
        from_llm = False

        if not answer:
            answer = self._get_llm_answer(request.query)
            from_llm = answer is not None

        if not answer:
            answer = "I'm sorry, I don't have an answer for that right now."
            from_llm = False

        return chatbot_pb2.AskQuestionResponse(answer=answer, from_llm=from_llm)
