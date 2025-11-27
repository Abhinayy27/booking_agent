"""
Client Agent - The orchestrator that handles user interactions and delegates to specialist agents.
Maintains conversation context and manages multi-turn conversations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from backend.protocol.schema import Task, Artifact, Message
from backend.protocol.registry import AgentRegistry
from backend.llm_service import LLMService
from backend.agents.search_agent import SearchAgent
from backend.agents.booking_agent import BookingAgent


class ClientAgent:
    """
    Main orchestrator agent that:
    1. Receives user messages
    2. Determines intent using LLM
    3. Selects appropriate specialist agent
    4. Manages conversation context
    5. Generates natural language responses
    """

    def __init__(self):
        self.id = "client_agent"
        self.registry = AgentRegistry()
        self.llm = LLMService()

        # Instantiate agents (In a real distributed system, these would be remote)
        self.agents = {"search_agent": SearchAgent(), "booking_agent": BookingAgent()}

        # Conversation context management
        self.conversation_history: List[Dict[str, Any]] = []
        self.last_search_results: List[Dict[str, Any]] = []
        self.last_booking_id: Optional[int] = None
        self.last_restaurant_id: Optional[int] = None
        self.user_name: Optional[str] = None  # Track user name for bookings
        self.pending_booking: Optional[Dict[str, Any]] = (
            None  # Track pending booking details
        )
        self.pending_modification: Optional[Dict[str, Any]] = (
            None  # Track pending modification (booking_id + what to change)
        )

    def process_message(self, user_message: str) -> str:
        """
        Main entry point for processing user messages.
        1. Determine intent using LLM with conversation context
        2. Check if we're in a pending booking flow
        3. Lookup agent in registry
        4. Resolve context references (e.g., "the first one")
        5. Create Task
        6. Execute Task on target agent
        7. Generate response using LLM
        8. Update conversation context
        """
        try:
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})

            # Check if we have a pending booking and user is providing name
            if self.pending_booking and self._is_name_provided(user_message):
                name = self._extract_name(user_message)
                if name:
                    self.user_name = name
                    self.pending_booking["details"]["customer_name"] = name

                    # Convert to new format: lookup restaurant_name, parse date/time
                    booking_details = self._prepare_booking_details(
                        self.pending_booking["details"]
                    )

                    if booking_details.get("error"):
                        response = booking_details["error"]
                        self.conversation_history.append(
                            {"role": "assistant", "content": response}
                        )
                        self.pending_booking = None
                        return response

                    # Create task with properly formatted details
                    task = Task(
                        source_agent_id=self.id,
                        target_agent_id="booking_agent",
                        intent="create_booking",
                        input_data={"action": "create", "details": booking_details},
                    )

                    artifact = self.agents["booking_agent"].execute(task)
                    self._update_context(
                        "create_booking", artifact, {"details": booking_details}
                    )

                    # Clear pending booking
                    self.pending_booking = None

                    # Generate response
                    response_text = self.llm.generate_response(
                        user_message, artifact.dict(), self.conversation_history
                    )

                    self.conversation_history.append(
                        {"role": "assistant", "content": response_text}
                    )
                    return response_text

            # Check if we have a pending modification and user is providing update details
            if self.pending_modification:
                # Extract update details from user message
                import re

                details = self.pending_modification.get("details", {})
                booking_id = details.get("booking_id")

                # Extract new time if mentioned
                user_message_lower = user_message.lower()
                time_keywords = [
                    "time",
                    "pm",
                    "am",
                    "o'clock",
                    "hour",
                    "at",
                    "to",
                    "change to",
                    "move to",
                    "reschedule to",
                ]
                has_time_intent = any(
                    keyword in user_message_lower for keyword in time_keywords
                )

                if has_time_intent and not details.get("new_time"):
                    time_match = re.search(
                        r"(\d{1,2})\s*(?::(\d{2}))?\s*(pm|am|PM|AM)?", user_message
                    )
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2)) if time_match.group(2) else 0
                        period = time_match.group(3)

                        if period:
                            period_lower = period.lower()
                            if period_lower == "pm":
                                if hour < 12:
                                    hour += 12
                                elif hour == 12:
                                    hour = 12
                            elif period_lower == "am":
                                if hour == 12:
                                    hour = 0

                        if hour < 0 or hour > 23:
                            hour = 19
                        if minute < 0 or minute > 59:
                            minute = 0

                        details["new_time"] = f"{hour:02d}:{minute:02d}"

                # Extract new party size if mentioned
                if not details.get("new_party_size"):
                    match = re.search(
                        r"(\d+)\s*(?:people|person|guests)", user_message, re.IGNORECASE
                    )
                    if match:
                        details["new_party_size"] = int(match.group(1))

                # If we have update details, proceed with modification
                if details.get("new_time") or details.get("new_party_size"):
                    # Create task with stored booking_id and extracted update details
                    task = Task(
                        source_agent_id=self.id,
                        target_agent_id="booking_agent",
                        intent="modify_booking",
                        input_data={"action": "modify", "details": details},
                    )

                    artifact = self.agents["booking_agent"].execute(task)
                    self._update_context(
                        "modify_booking", artifact, {"details": details}
                    )

                    # Clear pending modification
                    self.pending_modification = None

                    # Generate response
                    response_text = self.llm.generate_response(
                        user_message, artifact.dict(), self.conversation_history
                    )
                    self.conversation_history.append(
                        {"role": "assistant", "content": response_text}
                    )
                    return response_text
                else:
                    # Still no update details, ask again
                    response = "I found your booking ID. What would you like to change? Please specify:\n- New time (e.g., 'change to 8pm' or 'move to 7:30 pm')\n- New party size (e.g., 'change to 4 people')"
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

            # 1. Determine Intent with context
            analysis = self.llm.determine_intent(
                user_message, self.conversation_history
            )
            intent = analysis.get("intent")
            target_agent_id = analysis.get("target_agent")
            parameters = analysis.get("parameters", {})

            if not target_agent_id:
                response = "I'm not sure how to help with that. I can help you find restaurants or manage bookings. What would you like to do?"
                self.conversation_history.append(
                    {"role": "assistant", "content": response}
                )
                return response

            # 2. Lookup Agent (Validation)
            agent_card = self.registry.get_agent(target_agent_id)
            if not agent_card:
                response = f"I'm sorry, but I couldn't find the right service to handle your request. Please try rephrasing."
                self.conversation_history.append(
                    {"role": "assistant", "content": response}
                )
                return response

            # 3. Resolve context references and add missing booking information
            parameters = self._resolve_context_references(
                intent, parameters, user_message
            )

            # 4. Check if we need to ask for missing information (for bookings)
            if intent == "create_booking":
                details = parameters.get("details", {})
                if not details.get("customer_name") and not details.get("user_name"):
                    # Store pending booking and ask for name
                    self.pending_booking = parameters
                    response = "I'd be happy to help you make a reservation! Could you please tell me your name?"
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response
                if not details.get("restaurant_id") and not details.get(
                    "restaurant_name"
                ):
                    response = "I'd be happy to help you make a reservation! Which restaurant would you like to book? You can say 'the first one' from the search results, or specify a restaurant number."
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Prepare booking details in the new format
                booking_details = self._prepare_booking_details(details)
                if booking_details.get("error"):
                    response = booking_details["error"]
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Update parameters with properly formatted details
                parameters["details"] = booking_details
                parameters["action"] = "create"

            # Handle cancellation - validate booking_id and add action
            elif intent == "cancel_booking":
                details = parameters.get("details", {})
                booking_id = details.get("booking_id")

                if not booking_id:
                    response = "I'd be happy to help you cancel your reservation! Could you please provide your booking ID?"
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Ensure booking_id is an integer
                try:
                    details["booking_id"] = int(booking_id)
                except (ValueError, TypeError):
                    response = f"I couldn't understand the booking ID '{booking_id}'. Please provide a valid booking ID number."
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                parameters["details"] = details
                parameters["action"] = "cancel"

            # Handle modification - validate booking_id and ensure action is set
            elif intent == "modify_booking":
                details = parameters.get("details", {})
                booking_id = details.get("booking_id")

                if not booking_id:
                    response = "I'd be happy to help you modify your reservation! Could you please provide your booking ID?"
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Ensure booking_id is an integer
                try:
                    details["booking_id"] = int(booking_id)
                except (ValueError, TypeError):
                    response = f"I couldn't understand the booking ID '{booking_id}'. Please provide a valid booking ID number."
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Check if user provided what they want to change
                new_time = details.get("new_time")
                new_party_size = details.get("new_party_size")

                if not new_time and not new_party_size:
                    # Store pending modification with booking_id for next turn
                    self.pending_modification = {
                        "intent": intent,
                        "target_agent": target_agent_id,
                        "details": details,
                    }
                    response = "I found your booking ID. What would you like to change? Please specify:\n- New time (e.g., 'change to 8pm' or 'move to 7:30 pm')\n- New party size (e.g., 'change to 4 people')"
                    self.conversation_history.append(
                        {"role": "assistant", "content": response}
                    )
                    return response

                # Clear pending modification if we have all details
                self.pending_modification = None
                parameters["details"] = details
                parameters["action"] = "modify"

            # 5. Create Task
            task = Task(
                source_agent_id=self.id,
                target_agent_id=target_agent_id,
                intent=intent,
                input_data=parameters,
            )

            # 6. Execute Task
            target_agent = self.agents.get(target_agent_id)
            if not target_agent:
                response = f"Error: Agent {target_agent_id} is not available."
                self.conversation_history.append(
                    {"role": "assistant", "content": response}
                )
                return response

            artifact = target_agent.execute(task)

            # 7. Update context based on results
            self._update_context(intent, artifact, parameters)

            # 8. Generate Response
            response_text = self.llm.generate_response(
                user_message, artifact.dict(), self.conversation_history
            )

            # Add response to conversation history
            self.conversation_history.append(
                {"role": "assistant", "content": response_text}
            )

            return response_text

        except Exception as e:
            error_response = f"I encountered an error while processing your request: {str(e)}. Please try again or rephrase your question."
            self.conversation_history.append(
                {"role": "assistant", "content": error_response}
            )
            return error_response

    def _is_name_provided(self, message: str) -> bool:
        """Check if the message contains a name."""
        import re

        name_patterns = [
            r"(?:i'?m|i am|name is|my name is)\s+([A-Z][a-z]+)",
            r"([A-Z][a-z]+)\s+(?:here|speaking)",
            r"^([A-Z][a-z]+)$",  # Just a name
        ]
        for pattern in name_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False

    def _extract_name(self, message: str) -> Optional[str]:
        """Extract name from message."""
        import re

        name_patterns = [
            r"(?:i'?m|i am|name is|my name is)\s+([A-Z][a-z]+)",
            r"([A-Z][a-z]+)\s+(?:here|speaking)",
            r"^([A-Z][a-z]+)$",  # Just a name
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _prepare_booking_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare booking details in the format required by create_reservation.
        Maps from internal format to A2A specification format.

        Returns:
            Dict with customer_name, restaurant_name, time, date, party_size
            or {"error": "error message"} if preparation fails
        """
        import sqlite3
        from datetime import datetime
        from backend.config import Config

        # Get customer name
        customer_name = details.get("customer_name") or details.get("user_name")
        if not customer_name:
            customer_name = self.user_name

        # Get restaurant name from restaurant_id
        restaurant_id = details.get("restaurant_id")
        restaurant_name = details.get("restaurant_name")

        if not restaurant_name and restaurant_id:
            # Lookup restaurant name from ID
            try:
                conn = sqlite3.connect(Config.DB_PATH)
                c = conn.cursor()
                c.execute("SELECT name FROM restaurants WHERE id = ?", (restaurant_id,))
                result = c.fetchone()
                conn.close()

                if result:
                    restaurant_name = result[0]
                else:
                    return {"error": f"Restaurant with ID {restaurant_id} not found"}
            except Exception as e:
                return {"error": f"Error looking up restaurant: {str(e)}"}

        if not restaurant_name:
            return {"error": "Restaurant name or ID is required"}

        # Parse booking_time into date and time
        booking_time = details.get("booking_time")
        if booking_time:
            try:
                # Parse ISO datetime string
                if isinstance(booking_time, str):
                    # Handle format like "2025-11-29T20:30:00"
                    if "T" in booking_time:
                        dt = datetime.fromisoformat(booking_time.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromisoformat(booking_time)

                    date = dt.date().isoformat()  # YYYY-MM-DD
                    time = dt.time().strftime("%H:%M")  # HH:MM (24-hour format)
                else:
                    return {"error": "Invalid booking_time format"}
            except Exception as e:
                return {"error": f"Error parsing booking time: {str(e)}"}
        else:
            # Default to today at 7 PM
            dt = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
            if dt < datetime.now():
                dt += timedelta(days=1)
            date = dt.date().isoformat()
            time = dt.time().strftime("%H:%M")

        # Get party size
        party_size = details.get("party_size")
        if not party_size:
            party_size = 2  # Default
        try:
            party_size = int(party_size)
        except (ValueError, TypeError):
            return {"error": "Party size must be a valid number"}

        return {
            "customer_name": customer_name or "Guest",
            "restaurant_name": restaurant_name,
            "time": time,
            "date": date,
            "party_size": party_size,
        }

    def _resolve_context_references(
        self, intent: str, parameters: Dict[str, Any], user_message: str
    ) -> Dict[str, Any]:
        """
        Resolve context references like "the first one", "that Italian place", etc.
        Maps these to actual restaurant IDs or booking IDs from conversation history.
        """
        user_message_lower = user_message.lower()

        # Handle restaurant references for booking
        if intent == "create_booking":
            details = parameters.get("details", {})

            # Extract party size if not already extracted
            if not details.get("party_size"):
                # Try to extract from message like "for 2", "for 4 people"
                import re

                match = re.search(
                    r"for\s+(\d+)\s*(?:people|person|guests)?",
                    user_message,
                    re.IGNORECASE,
                )
                if match:
                    details["party_size"] = int(match.group(1))
                else:
                    details["party_size"] = 2  # Default

            # Extract booking time if not already extracted
            if not details.get("booking_time"):
                import re
                from datetime import datetime, timedelta

                # Extract date first (format: 29/11/25, 29-11-2025, Nov 29, etc.)
                date_obj = None
                date_patterns = [
                    r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",  # 29/11/25 or 29/11/2025
                    r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{2,4})",  # 29 Nov 2025
                ]

                for pattern in date_patterns:
                    date_match = re.search(pattern, user_message, re.IGNORECASE)
                    if date_match:
                        if "/" in pattern or "-" in pattern:
                            day, month, year = date_match.groups()
                            day, month, year = int(day), int(month), int(year)
                            if year < 100:
                                year += 2000
                            try:
                                date_obj = datetime(year, month, day).date()
                                break
                            except ValueError:
                                pass

                if not date_obj:
                    date_obj = datetime.now().date()

                # Extract time like "8:30 pm", "8:30pm", "8 pm", "20:30"
                time_match = re.search(
                    r"(\d{1,2})\s*(?::(\d{2}))?\s*(pm|am|PM|AM)?", user_message
                )
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                    period = time_match.group(3)

                    # Handle AM/PM conversion
                    if period:
                        period_lower = period.lower()
                        if period_lower == "pm":
                            if hour < 12:
                                hour += 12
                            elif hour == 12:
                                hour = 12  # 12pm = noon
                        elif period_lower == "am":
                            if hour == 12:
                                hour = 0  # 12am = midnight
                            # else hour stays as is (1am-11am)
                    else:
                        # 24-hour format assumed if no AM/PM
                        if hour > 23:
                            hour = hour % 24

                    # Ensure hour is valid (0-23)
                    if hour < 0 or hour > 23:
                        hour = 19  # Default to 7 PM if invalid

                    # Ensure minute is valid (0-59)
                    if minute < 0 or minute > 59:
                        minute = 0

                    try:
                        booking_dt = datetime.combine(
                            date_obj, datetime.min.time()
                        ).replace(hour=hour, minute=minute)
                        # If time is in the past and it's today, move to next day
                        if (
                            booking_dt < datetime.now()
                            and date_obj == datetime.now().date()
                        ):
                            booking_dt += timedelta(days=1)
                        details["booking_time"] = booking_dt.isoformat()
                    except ValueError as e:
                        # Fallback to default time
                        booking_dt = datetime.combine(
                            date_obj, datetime.min.time()
                        ).replace(hour=19, minute=0)
                        if booking_dt < datetime.now():
                            booking_dt += timedelta(days=1)
                        details["booking_time"] = booking_dt.isoformat()
                else:
                    # Default to 7 PM on the specified date (or today)
                    booking_dt = datetime.combine(
                        date_obj, datetime.min.time()
                    ).replace(hour=19, minute=0)
                    if booking_dt < datetime.now():
                        booking_dt += timedelta(days=1)
                    details["booking_time"] = booking_dt.isoformat()

            # Extract user name if not already extracted
            if not details.get("user_name") and not details.get("customer_name"):
                # Check if user provided their name in recent messages
                if self.user_name:
                    details["user_name"] = self.user_name
                    details["customer_name"] = self.user_name
                else:
                    # Try to extract name from message (e.g., "I'm John", "name is Sarah")
                    import re

                    name_patterns = [
                        r"(?:i'?m|i am|name is|my name is)\s+([A-Z][a-z]+)",
                        r"([A-Z][a-z]+)\s+(?:here|speaking)",
                    ]
                    for pattern in name_patterns:
                        name_match = re.search(pattern, user_message, re.IGNORECASE)
                        if name_match:
                            self.user_name = name_match.group(1)
                            details["user_name"] = self.user_name
                            details["customer_name"] = self.user_name
                            break

            # Check for restaurant ID references
            if not details.get("restaurant_id"):
                # Try to extract restaurant number (e.g., "restaurant 35", "restaurant x")
                import re

                restaurant_num_match = re.search(
                    r"restaurant\s+(\d+)", user_message, re.IGNORECASE
                )
                if restaurant_num_match:
                    restaurant_num = int(restaurant_num_match.group(1))
                    details["restaurant_id"] = restaurant_num
                # Check for ordinal references ("first one", "second one", etc.)
                elif "first" in user_message_lower or "1st" in user_message_lower:
                    if self.last_search_results:
                        details["restaurant_id"] = self.last_search_results[0].get("id")
                elif "second" in user_message_lower or "2nd" in user_message_lower:
                    if len(self.last_search_results) > 1:
                        details["restaurant_id"] = self.last_search_results[1].get("id")
                elif "third" in user_message_lower or "3rd" in user_message_lower:
                    if len(self.last_search_results) > 2:
                        details["restaurant_id"] = self.last_search_results[2].get("id")

                # If still not set and we have last restaurant, use it
                if not details.get("restaurant_id") and self.last_restaurant_id:
                    details["restaurant_id"] = self.last_restaurant_id

            parameters["details"] = details

        # Handle booking references for modification
        elif intent == "modify_booking":
            details = parameters.get("details", {})
            import re

            # Extract booking_id from user message if not already set
            if not details.get("booking_id"):
                # Try various patterns for booking ID
                booking_id_patterns = [
                    r"booking\s+id\s+is\s+(\d+)",
                    r"booking\s+id\s+(\d+)",
                    r"id\s+is\s+(\d+)",
                    r"\bid\s+(\d+)",
                    r"booking\s+#?(\d+)",
                    r"reservation\s+id\s+is\s+(\d+)",
                    r"reservation\s+id\s+(\d+)",
                    r"reservation\s+#?(\d+)",
                ]
                for pattern in booking_id_patterns:
                    match = re.search(pattern, user_message, re.IGNORECASE)
                    if match:
                        try:
                            details["booking_id"] = int(match.group(1))
                            break
                        except ValueError:
                            continue

                # Fallback: if still not found and message doesn't contain time/party size keywords,
                # try to extract standalone number
                if not details.get("booking_id"):
                    # Only extract if message doesn't contain time/party size keywords
                    if not re.search(
                        r"(?:time|pm|am|people|person|guests|change|modify|update)\s+\d+",
                        user_message,
                        re.IGNORECASE,
                    ):
                        standalone_num = re.search(r"\b(\d+)\b", user_message)
                        if standalone_num:
                            try:
                                potential_id = int(standalone_num.group(1))
                                # Only use if it's a reasonable booking ID (not a time like "2pm" or party size)
                                if (
                                    potential_id > 0 and potential_id < 10000
                                ):  # Reasonable range
                                    details["booking_id"] = potential_id
                            except ValueError:
                                pass

            # Extract new time ONLY if user explicitly mentions time-related keywords
            # Don't extract time if user only provided booking ID without mentioning time change
            if not details.get("new_time"):
                user_message_lower = user_message.lower()
                # Only extract time if user explicitly mentions time-related words
                time_keywords = [
                    "time",
                    "pm",
                    "am",
                    "o'clock",
                    "hour",
                    "at",
                    "to",
                    "change to",
                    "move to",
                    "reschedule to",
                ]
                has_time_intent = any(
                    keyword in user_message_lower for keyword in time_keywords
                )

                if has_time_intent:
                    time_match = re.search(
                        r"(\d{1,2})\s*(?::(\d{2}))?\s*(pm|am|PM|AM)?", user_message
                    )
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2)) if time_match.group(2) else 0
                        period = time_match.group(3)

                        # Handle AM/PM conversion properly
                        if period:
                            period_lower = period.lower()
                            if period_lower == "pm":
                                if hour < 12:
                                    hour += 12
                                elif hour == 12:
                                    hour = 12  # 12pm = noon
                            elif period_lower == "am":
                                if hour == 12:
                                    hour = 0  # 12am = midnight

                        # Ensure valid hour
                        if hour < 0 or hour > 23:
                            hour = 19  # Default to 7 PM
                        if minute < 0 or minute > 59:
                            minute = 0

                        # Format as 24-hour time string (HH:MM)
                        details["new_time"] = f"{hour:02d}:{minute:02d}"

            # Extract new party size if provided
            if not details.get("new_party_size"):
                match = re.search(
                    r"(\d+)\s*(?:people|person|guests)", user_message, re.IGNORECASE
                )
                if match:
                    details["new_party_size"] = int(match.group(1))

            # Final fallback to last_booking_id
            if not details.get("booking_id") and self.last_booking_id:
                details["booking_id"] = self.last_booking_id

            parameters["details"] = details

        # Handle cancellation
        elif intent == "cancel_booking":
            details = parameters.get("details", {})
            import re

            # Extract booking_id from user message if not already set
            if not details.get("booking_id"):
                # Try various patterns for booking ID
                booking_id_patterns = [
                    r"booking\s+id\s+is\s+(\d+)",
                    r"booking\s+id\s+(\d+)",
                    r"id\s+is\s+(\d+)",
                    r"\bid\s+(\d+)",
                    r"booking\s+#?(\d+)",
                    r"reservation\s+id\s+is\s+(\d+)",
                    r"reservation\s+id\s+(\d+)",
                    r"reservation\s+#?(\d+)",
                ]
                for pattern in booking_id_patterns:
                    match = re.search(pattern, user_message, re.IGNORECASE)
                    if match:
                        try:
                            details["booking_id"] = int(match.group(1))
                            break
                        except ValueError:
                            continue

                # Fallback: if still not found, try to extract standalone number
                if not details.get("booking_id"):
                    standalone_num = re.search(r"\b(\d+)\b", user_message)
                    if standalone_num:
                        try:
                            potential_id = int(standalone_num.group(1))
                            # Only use if it's a reasonable booking ID
                            if (
                                potential_id > 0 and potential_id < 10000
                            ):  # Reasonable range
                                details["booking_id"] = potential_id
                        except ValueError:
                            pass

            # Final fallback to last_booking_id
            if not details.get("booking_id") and self.last_booking_id:
                details["booking_id"] = self.last_booking_id

            parameters["details"] = details

        return parameters

    def _update_context(
        self, intent: str, artifact: Artifact, parameters: Dict[str, Any]
    ):
        """
        Update conversation context based on agent responses.
        """
        if artifact.status == "success":
            data = artifact.data

            # Update search results context
            if intent == "find_restaurants" and isinstance(data, list):
                self.last_search_results = data
                # Also update with restaurant IDs for easy reference
                print(f"Found {len(data)} restaurants: {[r.get('name') for r in data]}")

            # Update booking context
            if intent == "create_booking" and isinstance(data, dict):
                self.last_booking_id = data.get("booking_id")
                details = parameters.get("details", {})
                self.last_restaurant_id = details.get("restaurant_id")

            # Update restaurant context for modifications
            if intent == "modify_booking" and isinstance(data, dict):
                # Keep the same booking_id
                pass

    def reset_conversation(self):
        """Reset conversation context (useful for new sessions)."""
        self.conversation_history = []
        self.last_search_results = []
        self.last_booking_id = None
        self.last_restaurant_id = None
        self.user_name = None
        self.pending_booking = None
        self.pending_modification = None
