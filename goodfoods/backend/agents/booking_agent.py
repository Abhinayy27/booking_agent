"""
Booking Agent - Handles reservation creation, modification, and cancellation.
Acts as the Specialist Agent: Transaction Handler for restaurant reservations.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from backend.protocol.schema import Task, Artifact
from backend.config import Config

DB_PATH = Config.DB_PATH


class BookingAgent:
    """
    Specialized agent for managing restaurant reservations.
    Handles create, modify, and cancel operations with proper validation.
    """

    def __init__(self):
        self.id = "booking_agent"

    def execute(self, task: Task) -> Artifact:
        """
        Executes a booking task.
        Expected input_data: {"action": str, "details": dict}
        For create action, details should contain: customer_name, restaurant_name, time, date, party_size
        """
        try:
            action = task.input_data.get("action")
            details = task.input_data.get("details", {})

            if not action:
                raise ValueError(
                    "Action not specified. Must be 'create', 'modify', or 'cancel'"
                )

            if action == "create":
                result = self.create_reservation(
                    customer_name=details.get("customer_name"),
                    restaurant_name=details.get("restaurant_name"),
                    time=details.get("time"),
                    date=details.get("date"),
                    party_size=details.get("party_size"),
                )
            elif action == "modify":
                result = self.update_reservation(
                    booking_id=details.get("booking_id"),
                    action_type="UPDATE",
                    new_time=details.get("new_time"),
                    new_party_size=details.get("new_party_size"),
                )
            elif action == "cancel":
                result = self.update_reservation(
                    booking_id=details.get("booking_id"), action_type="CANCEL"
                )
            elif action == "check_availability":
                result = self._check_availability(details)
            else:
                raise ValueError(
                    f"Unknown action: {action}. Must be 'create', 'modify', 'cancel', or 'check_availability'"
                )

            # Format artifact based on result status
            if result.get("status") in ["CONFIRMED", "MODIFIED", "CANCELLED"]:
                return Artifact(
                    task_id=task.id,
                    producer_agent_id=self.id,
                    status="success",
                    data=result,
                )
            else:
                return Artifact(
                    task_id=task.id,
                    producer_agent_id=self.id,
                    status="failure",
                    data=result,
                    error_message=result.get("reason", "Operation failed"),
                )
        except ValueError as e:
            # User-facing errors (validation failures)
            return Artifact(
                task_id=task.id,
                producer_agent_id=self.id,
                status="failure",
                data={
                    "status": "FAILED",
                    "reason": str(e),
                    "details": "No booking was created.",
                },
                error_message=str(e),
            )
        except Exception as e:
            # System errors
            return Artifact(
                task_id=task.id,
                producer_agent_id=self.id,
                status="failure",
                data={
                    "status": "FAILED",
                    "reason": f"Database write error or concurrency conflict: {str(e)}",
                    "details": "No booking was created.",
                },
                error_message=f"Booking operation failed: {str(e)}",
            )

    def create_reservation(
        self,
        customer_name: str,
        restaurant_name: str,
        time: str,
        date: str,
        party_size: int,
    ) -> Dict[str, Any]:
        """
        Executes the final booking transaction, persists the reservation record to the database,
        and generates the confirmation artifact.

        This function must only be called when all parameters are valid and availability has been successfully verified.

        Args:
            customer_name: Customer's name (string)
            restaurant_name: Name of the restaurant (string)
            time: Booking time in 24-hour format, e.g., "19:00" (string)
            date: Booking date in ISO format, e.g., "YYYY-MM-DD" (string)
            party_size: Number of guests (integer)

        Returns:
            Dict with status "CONFIRMED" or "FAILED" and appropriate details
        """
        # Validate required parameters
        if not customer_name:
            return {
                "status": "FAILED",
                "reason": "customer_name is required",
                "details": "No booking was created.",
            }

        if not restaurant_name:
            return {
                "status": "FAILED",
                "reason": "restaurant_name is required",
                "details": "No booking was created.",
            }

        if not time:
            return {
                "status": "FAILED",
                "reason": "time is required",
                "details": "No booking was created.",
            }

        if not date:
            return {
                "status": "FAILED",
                "reason": "date is required",
                "details": "No booking was created.",
            }

        if not party_size or not isinstance(party_size, int) or party_size < 1:
            return {
                "status": "FAILED",
                "reason": "party_size must be a positive integer",
                "details": "No booking was created.",
            }

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            # Step 1: Lookup restaurant_id from restaurant_name
            c.execute(
                "SELECT id, capacity FROM restaurants WHERE name = ?",
                (restaurant_name,),
            )
            restaurant = c.fetchone()

            if not restaurant:
                conn.close()
                return {
                    "status": "FAILED",
                    "reason": f"Restaurant '{restaurant_name}' not found",
                    "details": "No booking was created.",
                }

            restaurant_id, capacity = restaurant

            # Validate party size against capacity
            if party_size > capacity:
                conn.close()
                return {
                    "status": "FAILED",
                    "reason": f"Party size ({party_size}) exceeds restaurant capacity ({capacity})",
                    "details": "No booking was created.",
                }

            # Combine date and time into ISO datetime format for database
            booking_datetime_str = f"{date}T{time}:00"
            try:
                booking_dt = datetime.fromisoformat(booking_datetime_str)
            except ValueError:
                conn.close()
                return {
                    "status": "FAILED",
                    "reason": f"Invalid date/time format. Expected date: YYYY-MM-DD, time: HH:MM",
                    "details": "No booking was created.",
                }

            # Check for booking conflicts (same restaurant, same time)
            c.execute(
                """
                SELECT COUNT(*) FROM bookings 
                WHERE restaurant_id = ? 
                AND booking_time = ? 
                AND status != 'cancelled'
            """,
                (restaurant_id, booking_datetime_str),
            )

            conflict_count = c.fetchone()[0]
            if conflict_count > 0:
                # Find alternative available times
                alternatives = self.find_alternative_times(
                    c, restaurant_id, booking_datetime_str, party_size, capacity
                )
                conn.close()

                if alternatives:
                    return {
                        "status": "FAILED",
                        "reason": f"Time slot {time} on {date} is already booked.",
                        "details": "No booking was created.",
                        "alternatives": alternatives,
                        "restaurant_name": restaurant_name,
                    }
                else:
                    return {
                        "status": "FAILED",
                        "reason": f"Time slot {time} on {date} is already booked. No nearby slots available for {party_size} people.",
                        "details": "No booking was created.",
                    }

            # Step 2: DB Transaction - Insert the new reservation record
            c.execute(
                """
                INSERT INTO bookings (restaurant_id, user_name, party_size, booking_time, status)
                VALUES (?, ?, ?, ?, 'confirmed')
            """,
                (restaurant_id, customer_name, party_size, booking_datetime_str),
            )

            # Step 3: Get ID - Retrieve the auto-generated unique booking_id
            booking_id = c.lastrowid

            conn.commit()
            conn.close()

            # Step 4: Dummy Email Generation - Trigger send_confirmation_email
            self.send_confirmation_email(
                booking_id=booking_id,
                customer_name=customer_name,
                restaurant_name=restaurant_name,
                date=date,
                time=time,
                party_size=party_size,
            )

            # Format time for display (convert 24-hour to readable format)
            try:
                hour, minute = map(int, time.split(":"))
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                display_time = f"{display_hour}:{minute:02d} {period}"
            except:
                display_time = time

            # Return success artifact
            return {
                "status": "CONFIRMED",
                "confirmation_id": str(booking_id),
                "message": "Reservation confirmed. Confirmation email simulated.",
                "details": f"{restaurant_name}, {date}, {display_time} for {party_size}.",
            }

        except sqlite3.Error as e:
            conn.rollback()
            conn.close()
            return {
                "status": "FAILED",
                "reason": f"Database write error: {str(e)}",
                "details": "No booking was created.",
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return {
                "status": "FAILED",
                "reason": f"Concurrency conflict or system error: {str(e)}",
                "details": "No booking was created.",
            }

    def send_confirmation_email(
        self,
        booking_id: int,
        customer_name: str,
        restaurant_name: str,
        date: str,
        time: str,
        party_size: int,
    ) -> None:
        """
        Dummy email generation routine.
        Prints the full email content to the console/log file as the "send" action.

        Args:
            booking_id: The booking confirmation ID
            customer_name: Customer's name
            restaurant_name: Restaurant name
            date: Booking date (ISO format)
            time: Booking time (24-hour format)
            party_size: Number of guests
        """
        # Format time for email display
        try:
            hour, minute = map(int, time.split(":"))
            period = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            if display_hour == 0:
                display_hour = 12
            display_time = f"{display_hour}:{minute:02d} {period}"
        except:
            display_time = time

        # Format date for email display
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            display_date = date_obj.strftime("%B %d, %Y")
        except:
            display_date = date

        subject = f"Confirmation: GoodFoods Reservation at {restaurant_name}"

        body = f"""
Dear {customer_name},

Your reservation has been confirmed!

Booking Details:
- Booking ID: {booking_id}
- Restaurant: {restaurant_name}
- Date: {display_date}
- Time: {display_time}
- Party Size: {party_size} {"guest" if party_size == 1 else "guests"}

We look forward to serving you!

Best regards,
GoodFoods Reservation System
"""

        # Print to console (dummy email sending)
        print("\n" + "=" * 70)
        print("EMAIL SENT (Dummy Implementation):")
        print("=" * 70)
        print(f"To: {customer_name.lower().replace(' ', '.')}@example.com")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("=" * 70 + "\n")

    def update_reservation(
        self,
        booking_id: int,
        action_type: str,
        new_time: Optional[str] = None,
        new_party_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes changes to an existing reservation or cancels it entirely.
        This function requires a valid booking_id to locate the record.
        It validates that the requested modification (time, size, or status) is permissible
        before committing the change to the database.

        Args:
            booking_id: The unique identifier of the reservation to be changed/cancelled (integer)
            action_type: Must be one of: "UPDATE", "CANCEL" (string)
            new_time: Optional; 24-hour format, e.g., "20:00". Required for time change requests (string)
            new_party_size: Optional; Required for party size changes (integer)

        Returns:
            Dict with status "MODIFIED", "CANCELLED", or "FAILED" and appropriate details
        """
        # Validate required parameters
        if not booking_id:
            return {
                "status": "FAILED",
                "reason": "booking_id is required",
                "details": "No changes were applied to the booking.",
            }

        if action_type not in ["UPDATE", "CANCEL"]:
            return {
                "status": "FAILED",
                "reason": f"Invalid action_type: {action_type}. Must be 'UPDATE' or 'CANCEL'",
                "details": "No changes were applied to the booking.",
            }

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            # Step 1: Retrieve Record - Fetch the current reservation details
            c.execute(
                """
                SELECT restaurant_id, user_name, party_size, booking_time, status 
                FROM bookings 
                WHERE id = ?
            """,
                (booking_id,),
            )

            booking = c.fetchone()
            if not booking:
                conn.close()
                return {
                    "status": "FAILED",
                    "reason": "Booking ID not found",
                    "details": "No changes were applied to the booking.",
                }

            restaurant_id, customer_name, current_party_size, current_time, status = (
                booking
            )

            if status == "cancelled":
                conn.close()
                return {
                    "status": "FAILED",
                    "reason": "Cannot modify or cancel an already cancelled booking",
                    "details": "No changes were applied to the booking.",
                }

            # Handle CANCEL action
            if action_type == "CANCEL":
                c.execute(
                    "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
                    (booking_id,),
                )

                conn.commit()
                conn.close()

                # Send cancellation email
                self.send_cancellation_email(booking_id, customer_name)

                return {
                    "status": "CANCELLED",
                    "confirmation_id": str(booking_id),
                    "message": "Reservation successfully cancelled.",
                    "details": "The booking has been removed from the system.",
                }

            # Handle UPDATE action
            if action_type == "UPDATE":
                # Validate that at least one field is being updated
                if not new_time and not new_party_size:
                    conn.close()
                    return {
                        "status": "FAILED",
                        "reason": "Must specify either new_time or new_party_size for UPDATE",
                        "details": "No changes were applied to the booking.",
                    }

                # Step 2: Validate Changes
                update_fields = []
                update_values = []
                final_time = current_time
                final_party_size = current_party_size

                # Validate new_time if provided
                if new_time:
                    try:
                        # Parse current booking time to get date
                        current_dt = datetime.fromisoformat(
                            current_time.replace("Z", "+00:00")
                        )
                        current_date = current_dt.date().isoformat()

                        # Combine date with new time
                        new_datetime_str = f"{current_date}T{new_time}:00"
                        new_dt = datetime.fromisoformat(new_datetime_str)

                        # Check if new time is in the past
                        if new_dt < datetime.now():
                            conn.close()
                            return {
                                "status": "FAILED",
                                "reason": "Cannot change booking to a time in the past",
                                "details": "No changes were applied to the booking.",
                            }

                        # Check for conflicts with other bookings
                        c.execute(
                            """
                            SELECT COUNT(*) FROM bookings 
                            WHERE restaurant_id = ? 
                            AND booking_time = ? 
                            AND id != ?
                            AND status != 'cancelled'
                        """,
                            (restaurant_id, new_datetime_str, booking_id),
                        )

                        if c.fetchone()[0] > 0:
                            conn.close()
                            return {
                                "status": "FAILED",
                                "reason": f"Requested time {new_time} conflicts with existing booking",
                                "details": "No changes were applied to the booking.",
                            }

                        update_fields.append("booking_time = ?")
                        update_values.append(new_datetime_str)
                        final_time = new_datetime_str
                    except ValueError as e:
                        conn.close()
                        return {
                            "status": "FAILED",
                            "reason": f"Invalid new_time format. Expected 24-hour format (HH:MM): {str(e)}",
                            "details": "No changes were applied to the booking.",
                        }

                # Validate new_party_size if provided
                if new_party_size:
                    try:
                        new_party_size = int(new_party_size)
                        if new_party_size < 1:
                            conn.close()
                            return {
                                "status": "FAILED",
                                "reason": "Party size must be at least 1",
                                "details": "No changes were applied to the booking.",
                            }

                        # Check restaurant capacity
                        c.execute(
                            "SELECT capacity FROM restaurants WHERE id = ?",
                            (restaurant_id,),
                        )
                        capacity = c.fetchone()[0]
                        if new_party_size > capacity:
                            conn.close()
                            return {
                                "status": "FAILED",
                                "reason": f"Requested party size ({new_party_size}) exceeds restaurant capacity ({capacity})",
                                "details": "No changes were applied to the booking.",
                            }

                        update_fields.append("party_size = ?")
                        update_values.append(new_party_size)
                        final_party_size = new_party_size
                    except (ValueError, TypeError):
                        conn.close()
                        return {
                            "status": "FAILED",
                            "reason": "new_party_size must be a valid integer",
                            "details": "No changes were applied to the booking.",
                        }

                # Step 3: DB Update - Commit the validated changes
                if update_fields:
                    update_values.append(booking_id)
                    query = (
                        f"UPDATE bookings SET {', '.join(update_fields)} WHERE id = ?"
                    )
                    c.execute(query, update_values)

                    if c.rowcount == 0:
                        conn.close()
                        return {
                            "status": "FAILED",
                            "reason": "Failed to update booking",
                            "details": "No changes were applied to the booking.",
                        }

                    conn.commit()

                    # Get restaurant name for email
                    c.execute(
                        "SELECT name FROM restaurants WHERE id = ?", (restaurant_id,)
                    )
                    restaurant_name = c.fetchone()[0]

                    conn.close()

                    # Step 4: Dummy Email Generation
                    self.send_modification_email(
                        booking_id=booking_id,
                        customer_name=customer_name,
                        restaurant_name=restaurant_name,
                        new_time=new_time if new_time else None,
                        new_party_size=new_party_size if new_party_size else None,
                        current_time=current_time,
                        current_party_size=current_party_size,
                    )

                    # Format details for response
                    details_parts = []
                    if new_time:
                        # Format time for display
                        try:
                            hour, minute = map(int, new_time.split(":"))
                            period = "AM" if hour < 12 else "PM"
                            display_hour = hour if hour <= 12 else hour - 12
                            if display_hour == 0:
                                display_hour = 12
                            display_time = f"{display_hour}:{minute:02d} {period}"
                        except:
                            display_time = new_time
                        details_parts.append(f"Time: {display_time}")

                    if new_party_size:
                        details_parts.append(f"Party Size: {new_party_size}")

                    details_str = (
                        ", ".join(details_parts)
                        if details_parts
                        else "No changes specified"
                    )

                    return {
                        "status": "MODIFIED",
                        "confirmation_id": str(booking_id),
                        "message": "Reservation successfully modified. New details confirmed.",
                        "details": details_str + ".",
                    }
                else:
                    conn.close()
                    return {
                        "status": "FAILED",
                        "reason": "No valid changes to apply",
                        "details": "No changes were applied to the booking.",
                    }

        except sqlite3.Error as e:
            conn.rollback()
            conn.close()
            return {
                "status": "FAILED",
                "reason": f"Database error: {str(e)}",
                "details": "No changes were applied to the booking.",
            }
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return {
                "status": "FAILED",
                "reason": f"System error: {str(e)}",
                "details": "No changes were applied to the booking.",
            }

    def send_modification_email(
        self,
        booking_id: int,
        customer_name: str,
        restaurant_name: str,
        new_time: Optional[str] = None,
        new_party_size: Optional[int] = None,
        current_time: Optional[str] = None,
        current_party_size: Optional[int] = None,
    ) -> None:
        """
        Dummy email generation for modification notifications.
        Prints the full email content to the console/log file.

        Args:
            booking_id: The booking ID
            customer_name: Customer's name
            restaurant_name: Restaurant name
            new_time: New booking time (24-hour format)
            new_party_size: New party size
            current_time: Current booking time (for reference)
            current_party_size: Current party size (for reference)
        """
        subject = f"[Modification] Confirmed: GoodFoods Reservation ID #{booking_id}"

        # Build body message based on what changed
        changes = []
        if new_time:
            # Format time for display
            try:
                hour, minute = map(int, new_time.split(":"))
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                display_time = f"{display_hour}:{minute:02d} {period}"
            except:
                display_time = new_time
            changes.append(f"Your reservation time has been moved to {display_time}.")

        if new_party_size:
            changes.append(
                f"Your party size has been updated to {new_party_size} {'guest' if new_party_size == 1 else 'guests'}."
            )

        if not changes:
            changes.append("Your reservation has been updated.")

        body = f"""
Dear {customer_name},

Your reservation has been successfully modified!

Booking Details:
- Booking ID: {booking_id}
- Restaurant: {restaurant_name}

Changes Made:
{chr(10).join(changes)}

We look forward to serving you!

Best regards,
GoodFoods Reservation System
"""

        # Print to console (dummy email sending)
        print("\n" + "=" * 70)
        print("EMAIL SENT (Dummy Implementation):")
        print("=" * 70)
        print(f"To: {customer_name.lower().replace(' ', '.')}@example.com")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("=" * 70 + "\n")

    def send_cancellation_email(self, booking_id: int, customer_name: str) -> None:
        """
        Dummy email generation for cancellation notifications.
        Prints the full email content to the console/log file.

        Args:
            booking_id: The booking ID
            customer_name: Customer's name
        """
        subject = f"[Cancellation] Confirmed: GoodFoods Reservation ID #{booking_id}"

        body = f"""
Dear {customer_name},

Your reservation has been successfully cancelled.

Booking Details:
- Booking ID: {booking_id}

Your reservation has been removed from the system.

If you need to make a new reservation, please don't hesitate to contact us.

Best regards,
GoodFoods Reservation System
"""

        # Print to console (dummy email sending)
        print("\n" + "=" * 70)
        print("EMAIL SENT (Dummy Implementation):")
        print("=" * 70)
        print(f"To: {customer_name.lower().replace(' ', '.')}@example.com")
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("=" * 70 + "\n")

    def _modify_booking(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modify an existing booking (typically change time or party size).
        """
        booking_id = details.get("booking_id")
        new_time = details.get("new_time")
        new_party_size = details.get("new_party_size")

        if not booking_id:
            raise ValueError("Booking ID is required for modification")

        if not new_time and not new_party_size:
            raise ValueError(
                "Must specify either new_time or new_party_size to modify booking"
            )

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            # Get existing booking
            c.execute(
                """
                SELECT restaurant_id, party_size, booking_time, status 
                FROM bookings 
                WHERE id = ?
            """,
                (booking_id,),
            )

            booking = c.fetchone()
            if not booking:
                raise ValueError(f"Booking with ID {booking_id} not found")

            restaurant_id, current_party_size, current_time, status = booking

            if status == "cancelled":
                raise ValueError("Cannot modify a cancelled booking")

            # Validate new time if provided
            if new_time:
                try:
                    new_dt = datetime.fromisoformat(new_time.replace("Z", "+00:00"))
                    if new_dt < datetime.now():
                        raise ValueError("Cannot change booking to a time in the past")
                except ValueError as e:
                    if "Cannot change" in str(e):
                        raise
                    raise ValueError(
                        f"Invalid new_time format. Please use ISO format (YYYY-MM-DDTHH:MM:SS)"
                    )

                # Check for conflicts with new time
                c.execute(
                    """
                    SELECT COUNT(*) FROM bookings 
                    WHERE restaurant_id = ? 
                    AND booking_time = ? 
                    AND id != ?
                    AND status != 'cancelled'
                """,
                    (restaurant_id, new_time, booking_id),
                )

                if c.fetchone()[0] > 0:
                    raise ValueError(
                        f"Time slot {new_time} is already booked. Please choose another time."
                    )

            # Validate new party size if provided
            if new_party_size:
                try:
                    new_party_size = int(new_party_size)
                    if new_party_size < 1:
                        raise ValueError("Party size must be at least 1")

                    # Check restaurant capacity
                    c.execute(
                        "SELECT capacity FROM restaurants WHERE id = ?",
                        (restaurant_id,),
                    )
                    capacity = c.fetchone()[0]
                    if new_party_size > capacity:
                        raise ValueError(
                            f"Party size ({new_party_size}) exceeds restaurant capacity ({capacity})"
                        )
                except (ValueError, TypeError) as e:
                    if "Party size" in str(e) or "exceeds" in str(e):
                        raise
                    raise ValueError("Party size must be a valid number")

            # Update booking
            update_fields = []
            update_values = []

            if new_time:
                update_fields.append("booking_time = ?")
                update_values.append(new_time)

            if new_party_size:
                update_fields.append("party_size = ?")
                update_values.append(new_party_size)

            if update_fields:
                update_values.append(booking_id)
                query = f"UPDATE bookings SET {', '.join(update_fields)} WHERE id = ?"
                c.execute(query, update_values)

                if c.rowcount == 0:
                    raise ValueError("Failed to update booking")

                conn.commit()

                # Get updated booking info
            c.execute(
                """
                SELECT r.name, b.booking_time, b.party_size 
                FROM bookings b 
                JOIN restaurants r ON b.restaurant_id = r.id 
                WHERE b.id = ?
            """,
                (booking_id,),
            )

            res_name, final_time, final_party_size = c.fetchone()

            return {
                "booking_id": booking_id,
                "status": "modified",
                "restaurant_name": res_name,
                "new_time": final_time,
                "party_size": final_party_size,
            }
        finally:
            conn.close()

    def _cancel_booking(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cancel an existing booking.
        """
        booking_id = details.get("booking_id")

        if not booking_id:
            raise ValueError("Booking ID is required for cancellation")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            # Check if booking exists
            c.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,))
            booking = c.fetchone()

            if not booking:
                raise ValueError(f"Booking with ID {booking_id} not found")

            if booking[0] == "cancelled":
                raise ValueError("Booking is already cancelled")

            # Cancel booking
            c.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,)
            )

            if c.rowcount == 0:
                raise ValueError("Failed to cancel booking")

            conn.commit()

            return {"booking_id": booking_id, "status": "cancelled"}
        finally:
            conn.close()

    def _check_availability(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check availability for a restaurant at a given time.
        """
        restaurant_id = details.get("restaurant_id")
        booking_time = details.get("booking_time")
        party_size = details.get("party_size", 1)

        if not restaurant_id:
            raise ValueError("Restaurant ID is required")
        if not booking_time:
            raise ValueError("Booking time is required")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            # Get restaurant capacity
            c.execute(
                "SELECT capacity, name FROM restaurants WHERE id = ?", (restaurant_id,)
            )
            res = c.fetchone()
            if not res:
                raise ValueError(f"Restaurant with ID {restaurant_id} not found")

            capacity, res_name = res

            # Check existing bookings at this time
            c.execute(
                """
                SELECT SUM(party_size) FROM bookings 
                WHERE restaurant_id = ? 
                AND booking_time = ? 
                AND status != 'cancelled'
            """,
                (restaurant_id, booking_time),
            )

            booked_seats = c.fetchone()[0] or 0
            available_seats = capacity - booked_seats

            is_available = available_seats >= party_size

            return {
                "restaurant_id": restaurant_id,
                "restaurant_name": res_name,
                "booking_time": booking_time,
                "available": is_available,
                "available_seats": available_seats,
                "capacity": capacity,
                "requested_party_size": party_size,
            }
        finally:
            conn.close()

    def find_alternative_times(
        self,
        cursor,
        restaurant_id: int,
        requested_datetime_str: str,
        party_size: int,
        capacity: int,
    ) -> List[str]:
        """
        Find alternative available time slots when the requested time is booked.
        Checks ±2 hours around the requested time in 1-hour increments.

        Args:
            cursor: Active database cursor
            restaurant_id: Restaurant ID
            requested_datetime_str: Requested time in ISO format
            party_size: Number of guests
            capacity: Restaurant capacity

        Returns:
            List of available time slots in display format (e.g., "6:00 PM", "8:00 PM")
        """
        try:
            requested_dt = datetime.fromisoformat(
                requested_datetime_str.replace("Z", "+00:00")
            )
        except ValueError:
            return []

        alternatives = []

        # Check time slots: -2h, -1h, +1h, +2h
        time_offsets = [-2, -1, 1, 2]

        for offset in time_offsets:
            check_dt = requested_dt + timedelta(hours=offset)

            # Don't suggest times in the past
            if check_dt < datetime.now():
                continue
            
            # Enforce business hours (e.g., 11 AM to 10 PM)
            if check_dt.hour < 11 or check_dt.hour >= 22:
                continue

            check_datetime_str = check_dt.isoformat()

            # Check if this slot is available
            cursor.execute(
                """
                SELECT COUNT(*) FROM bookings 
                WHERE restaurant_id = ? 
                AND booking_time = ? 
                AND status != 'cancelled'
                """,
                (restaurant_id, check_datetime_str),
            )

            if cursor.fetchone()[0] == 0:  # No conflicts
                # Format time for display
                hour = check_dt.hour
                minute = check_dt.minute
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12

                time_str = f"{display_hour}:{minute:02d} {period}"
                alternatives.append(time_str)

        return alternatives
