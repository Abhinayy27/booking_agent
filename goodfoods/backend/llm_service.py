"""
LLM Service using OpenAI API with gpt-4o-mini model.
Handles intent detection, entity extraction, agent selection, and response generation.
"""

import json
import re
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from backend.config import Config
from backend.protocol.registry import AgentRegistry


class LLMService:
    """
    LLM service using OpenAI API for intelligent intent detection and response generation.
    Implements proper tool calling architecture where LLM determines intent dynamically.
    """

    def __init__(self):
        """Initialize LLM service with OpenAI client."""
        try:
            # Always read from environment directly
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            self.client = OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.registry = AgentRegistry()
        except (ValueError, Exception) as e:
            # If API key not set, create a mock client that will fail gracefully
            print(f"[WARNING] {e}")
            self.client = None
            self.model = None

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        """
        Call OpenAI API with given prompts.
        Returns the response text or raises an exception.
        """
        if not self.client:
            raise ValueError(
                "OpenAI API client not initialized. Please set OPENAI_API_KEY environment variable."
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"LLM API call failed: {str(e)}")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        """
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        # Try to find JSON object in the text
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try to extract key-value pairs
            return {"error": "Failed to parse JSON response", "raw": text}

    def determine_intent(
        self,
        user_input: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes user input to determine intent, extract parameters, and select target agent.
        Uses LLM to dynamically determine intent rather than hardcoded rules.

        Args:
            user_input: User's message
            conversation_context: Previous messages for context (optional)

        Returns:
            Dictionary with 'intent', 'target_agent', and 'parameters'
        """
        # Build context string if available
        context_str = ""
        if conversation_context:
            recent_messages = conversation_context[-3:]  # Last 3 messages for context
            context_str = "\n\nRecent conversation:\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_str += f"{role}: {content}\n"

        # Get available agents and their capabilities
        agents = self.registry.list_all_agents()
        agent_info = []
        for agent in agents:
            if agent.id != "client_agent":  # Don't include client agent in selection
                agent_info.append(
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "description": agent.description,
                        "capabilities": agent.capabilities,
                    }
                )

        system_prompt = """You are an intelligent intent classifier for a restaurant reservation system.
Your task is to analyze user messages and determine:
1. The user's intent (search, book, modify, cancel, or general_query)
2. Which agent should handle the request (search_agent or booking_agent)
3. Extract relevant parameters from the user's message

Available agents:
- search_agent: Handles finding restaurants based on cuisine, location, price, ambiance, etc.
- booking_agent: Handles creating, modifying, or cancelling reservations

Intents:
- find_restaurants: User wants to search/find/recommend restaurants
- create_booking: User wants to make a reservation
- modify_booking: User wants to change an existing reservation (UPDATE action)
- cancel_booking: User wants to cancel a reservation (CANCEL action)
- general_query: General questions that don't require agent action

For search queries, extract filters like:
- cuisine (Italian, Chinese, etc.)
- location (Downtown, Uptown, etc.)
- ambiance (Romantic, Family-friendly, etc.)
- price_range (1-4 scale, or extract budget like "under $100")
- min_rating (if mentioned)

For booking queries, extract:
- restaurant_id (if available - the system will try to map "first one", "second one" references)
- party_size (number of people, look for "for X people/persons")
- booking_time (extract time like "7pm", "19:00" - format as ISO: YYYY-MM-DDTHH:MM:SS. IMPORTANT: Use the local time implied by the user, do NOT convert to UTC. If no date is specified, assume today.)
- user_name (if provided, otherwise leave empty for "Guest")

For modification queries, extract:
- booking_id (REQUIRED - look for patterns like "booking ID 2", "ID is 5", "booking #3", "reservation ID 4", or just a number if context suggests it's a booking ID)
- new_time (new booking time in 24-hour format like "20:00" or extract from "8pm", "8:30 pm", etc.)
- new_party_size (if mentioned, extract number of people/guests)

For cancellation queries, extract:
- booking_id (REQUIRED - look for patterns like "booking ID 2", "ID is 5", "booking #3", "reservation ID 4", or just a number if context suggests it's a booking ID)

Always respond with valid JSON in this exact format:
{
    "intent": "intent_name",
    "target_agent": "agent_id",
    "parameters": {
        // Relevant parameters based on intent
    }
}"""

        user_prompt = f"""User message: {user_input}
{context_str}

Analyze the user's intent and extract parameters. Return JSON only."""

        try:
            response_text = self._call_llm(
                system_prompt, user_prompt, max_tokens=800, temperature=0.2
            )
            result = self._parse_json_response(response_text)

            # Validate and set defaults
            intent = result.get("intent", "unknown")
            target_agent = result.get("target_agent")
            parameters = result.get("parameters", {})

            # Handle context references (e.g., "the first one", "that Italian place")
            if conversation_context and intent in ["create_booking", "modify_booking"]:
                # This will be handled by ClientAgent's context management
                pass

            # Normalize intent names
            if intent == "search" or intent == "find":
                intent = "find_restaurants"
            elif intent == "book" or intent == "reserve":
                intent = "create_booking"

            # Ensure target_agent is set based on intent if not provided
            if not target_agent:
                if intent == "find_restaurants":
                    target_agent = "search_agent"
                elif intent in ["create_booking", "modify_booking", "cancel_booking"]:
                    target_agent = "booking_agent"
                else:
                    target_agent = None

            return {
                "intent": intent,
                "target_agent": target_agent,
                "parameters": parameters,
            }

        except Exception as e:
            # Fallback to simple keyword-based detection
            print(f"[WARNING] LLM call failed: {e}. Using fallback detection.")
            return self._fallback_intent_detection(user_input)

    def _fallback_intent_detection(self, user_input: str) -> Dict[str, Any]:
        """
        Fallback intent detection using simple keyword matching.
        Used when LLM API fails.
        """
        user_input_lower = user_input.lower()

        # Search intent
        if any(
            word in user_input_lower
            for word in [
                "find",
                "suggest",
                "recommend",
                "looking for",
                "search",
                "show me",
            ]
        ):
            filters = {}
            # Simple extraction
            for cuisine in [
                "italian",
                "chinese",
                "mediterranean",
                "indian",
                "japanese",
                "mexican",
                "french",
                "thai",
            ]:
                if cuisine in user_input_lower:
                    filters["cuisine"] = cuisine.capitalize()
                    break

            if "romantic" in user_input_lower:
                filters["ambiance"] = "Romantic"
            elif "family" in user_input_lower:
                filters["ambiance"] = "Family-friendly"

            return {
                "intent": "find_restaurants",
                "target_agent": "search_agent",
                "parameters": {"filters": filters},
            }

        # Booking intent
        if any(
            word in user_input_lower
            for word in ["book", "reservation", "reserve", "table"]
        ):
            return {
                "intent": "create_booking",
                "target_agent": "booking_agent",
                "parameters": {"action": "create", "details": {}},
            }

        # Modification intent
        if any(
            word in user_input_lower
            for word in ["change", "modify", "update", "push", "move"]
        ):
            return {
                "intent": "modify_booking",
                "target_agent": "booking_agent",
                "parameters": {"action": "modify", "details": {}},
            }

        return {"intent": "unknown", "target_agent": None, "parameters": {}}

    def generate_response(
        self,
        user_input: str,
        agent_response: Dict[str, Any],
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generates a natural language response based on the agent's output.
        Uses LLM to create conversational, helpful responses.
        """
        data = agent_response.get("data")
        status = agent_response.get("status")
        error_message = agent_response.get("error_message")

        system_prompt = """You are a friendly restaurant concierge assistant for GoodFoods.
Your role is to communicate restaurant search results and booking confirmations to customers in a natural, helpful way.
Be concise, friendly, and informative. 

For restaurant search results:
- Format each restaurant as a numbered list item (1., 2., etc.)
- Include the restaurant name followed by a cuisine flag emoji (🇮🇹 for Italian, 🇨🇳 for Chinese, 🇯🇵 for Japanese, 🇲🇽 for Mexican, 🇫🇷 for French, 🇹🇭 for Thai, 🇬🇷 for Mediterranean, 🇮🇳 for Indian, etc.)
- Write a descriptive paragraph (3-4 sentences) instead of bullet points
- Make it sound natural and engaging, like you're describing the restaurant to a friend
- Include: cuisine type, location, rating, ambiance, price range, and capacity naturally within the paragraph
- Use phrases like "This is a fantastic choice for...", "It has garnered exceptional feedback...", "The restaurant offers...", etc.
- Separate each restaurant with a blank line (----)

For booking confirmations, include booking ID, restaurant name, time, and party size.
For errors, be apologetic and helpful."""

        # Build user prompt based on response type
        if status == "failure":
            # Check if there are alternative times available
            alternatives = (
                data.get("alternatives", []) if isinstance(data, dict) else []
            )

            if alternatives:
                alt_text = ", ".join(alternatives)
                restaurant_name = data.get("restaurant_name", "the restaurant")
                user_prompt = f"""The user asked: "{user_input}"
The requested time slot is already booked at {restaurant_name}.
However, these alternative times are available on the same day: {alt_text}

Generate a helpful, apologetic response that:
1. Explains the time conflict
2. Suggests the alternative times in a friendly, conversational way
3. Asks if they'd like to book one of the alternatives instead"""
            else:
                user_prompt = f"""The user asked: "{user_input}"
The system encountered an error: {error_message}
Generate a helpful, apologetic response that explains the issue in user-friendly terms."""
        elif isinstance(data, list):  # Search results
            if not data:
                user_prompt = f"""The user asked: "{user_input}"
No restaurants were found matching their criteria.
Generate a helpful response suggesting they try different search criteria."""
            else:
                # Separate exact matches from nearby locations
                exact_matches = [r for r in data if not r.get("_is_nearby", False)]
                nearby_results = [r for r in data if r.get("_is_nearby", False)]

                # Format exact match restaurants with all details for LLM to generate narrative
                exact_data = []
                if exact_matches:
                    for r in exact_matches[:5]:
                        exact_data.append(
                            {
                                "name": r.get("name", "Unknown"),
                                "cuisine": r.get("cuisine", "Unknown"),
                                "ambiance": r.get("ambiance", "Unknown"),
                                "location": r.get("location", "Unknown"),
                                "rating": r.get("rating", "N/A"),
                                "price_range": r.get("price_range", "N/A"),
                                "capacity": r.get("capacity", "N/A"),
                            }
                        )

                # Format nearby restaurants with all details
                nearby_data = []
                if nearby_results:
                    for r in nearby_results[:3]:
                        nearby_data.append(
                            {
                                "name": r.get("name", "Unknown"),
                                "cuisine": r.get("cuisine", "Unknown"),
                                "ambiance": r.get("ambiance", "Unknown"),
                                "location": r.get("location", "Unknown"),
                                "rating": r.get("rating", "N/A"),
                                "price_range": r.get("price_range", "N/A"),
                                "capacity": r.get("capacity", "N/A"),
                            }
                        )

                user_prompt = f"""The user asked: "{user_input}"
Here are the search results:"""

                if exact_data:
                    restaurants_info = "\n\n".join(
                        [
                            f"Restaurant {i + 1}: {r['name']} | Cuisine: {r['cuisine']} | Location: {r['location']} | "
                            f"Rating: {r['rating']}/5.0 | Ambiance: {r['ambiance']} | "
                            f"Price Range: {r['price_range']}/4 | Capacity: {r['capacity']} seats"
                            for i, r in enumerate(exact_data)
                        ]
                    )
                    user_prompt += f"\n\nRestaurants in the requested location:\n{restaurants_info}"

                if nearby_data:
                    nearby_info = "\n\n".join(
                        [
                            f"Restaurant {i + 1}: {r['name']} | Cuisine: {r['cuisine']} | Location: {r['location']} | "
                            f"Rating: {r['rating']}/5.0 | Ambiance: {r['ambiance']} | "
                            f"Price Range: {r['price_range']}/4 | Capacity: {r['capacity']} seats"
                            for i, r in enumerate(nearby_data)
                        ]
                    )
                    user_prompt += f"\n\nSome other {nearby_data[0].get('cuisine', 'Italian')} restaurants nearby to the requested location:\n{nearby_info}"

                user_prompt += "\n\nGenerate a friendly response presenting these restaurants. Format each restaurant as:\n- Numbered list item (1., 2., etc.)\n- Restaurant name followed by cuisine flag emoji\n- A descriptive paragraph (3-4 sentences) describing the restaurant naturally\n- Include all details (cuisine, location, rating, ambiance, price range, capacity) within the paragraph\n- Separate each restaurant with a blank line (----)\n- Make it sound engaging and natural, like describing to a friend"
        elif isinstance(data, dict):  # Booking result
            if "booking_id" in data:
                if data.get("status") == "confirmed":
                    user_prompt = f"""The user asked: "{user_input}"
Booking confirmed successfully:
- Booking ID: {data.get("booking_id")}
- Restaurant: {data.get("restaurant_name")}
- Time: {data.get("time")}
- Party Size: {data.get("party_size", "Not specified")}

A confirmation email has been sent to the user.

Generate a friendly confirmation message that includes the booking details and mentions that a confirmation email has been sent."""
                elif data.get("status") == "modified":
                    user_prompt = f"""The user asked: "{user_input}"
Reservation updated successfully:
- Booking ID: {data.get("booking_id")}
- New Time: {data.get("new_time")}

Generate a friendly confirmation message."""
                elif data.get("status") == "cancelled":
                    user_prompt = f"""The user asked: "{user_input}"
Reservation cancelled:
- Booking ID: {data.get("booking_id")}

Generate a friendly confirmation message."""
                else:
                    user_prompt = f"""The user asked: "{user_input}"
Booking operation completed: {data}
Generate an appropriate response."""
            else:
                user_prompt = f"""The user asked: "{user_input}"
System response: {data}
Generate an appropriate response."""
        else:
            user_prompt = f"""The user asked: "{user_input}"
System processed the request: {agent_response}
Generate an appropriate response."""

        try:
            response_text = self._call_llm(
                system_prompt, user_prompt, max_tokens=2000, temperature=0.7
            )
            return response_text.strip()
        except Exception as e:
            # Fallback to template-based responses
            print(f"[WARNING] LLM response generation failed: {e}. Using fallback.")
            return self._fallback_response_generation(user_input, agent_response)

    def _fallback_response_generation(
        self, user_input: str, agent_response: Dict[str, Any]
    ) -> str:
        """
        Fallback response generation using templates.
        Used when LLM API fails.
        """
        data = agent_response.get("data")
        status = agent_response.get("status")

        if status == "failure":
            return f"I'm sorry, but I encountered an error: {agent_response.get('error_message', 'Unknown error')}. Please try again or rephrase your request."

        if isinstance(data, list):  # Search results
            if not data:
                return "I couldn't find any restaurants matching your criteria. Would you like to try different search terms?"

            response = "Here are some recommendations:\n\n"
            for i, r in enumerate(data[:5], 1):
                response += f"{i}. **{r.get('name', 'Unknown')}**\n"
                response += f"   Cuisine: {r.get('cuisine', 'Unknown')} | "
                response += f"Location: {r.get('location', 'Unknown')} | "
                response += f"Ambiance: {r.get('ambiance', 'Unknown')}\n"
                response += f"   Rating: {r.get('rating', 'N/A')}/5.0 | "
                response += f"Price Range: {r.get('price_range', 'N/A')}/4\n\n"
            return response

        if isinstance(data, dict):  # Booking result
            if "booking_id" in data:
                if data.get("status") == "confirmed":
                    return f"Great! I've booked a table at {data.get('restaurant_name', 'the restaurant')} for {data.get('time', 'the requested time')}. Your booking ID is {data.get('booking_id')}."
                elif data.get("status") == "modified":
                    return f"Done! Your reservation has been updated to {data.get('new_time', 'the new time')}."
                elif data.get("status") == "cancelled":
                    return f"Your reservation (ID: {data.get('booking_id')}) has been cancelled."

        return (
            "I've processed your request. Is there anything else I can help you with?"
        )
