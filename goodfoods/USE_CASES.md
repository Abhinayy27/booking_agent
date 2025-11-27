# GoodFoods Reservation System - Use Cases

This document details the use cases for the GoodFoods AI Reservation System, following standard use case documentation practices.

---

## Use Case 1: Smart Restaurant Discovery

**Use Case ID**: UC-001  
**Use Case Name**: Smart Restaurant Discovery  
**Priority**: High  
**Status**: Implemented

### Description
Users can search for restaurants using natural language queries with multiple constraints (cuisine, location, price, ambiance, etc.). The system intelligently interprets the query, filters restaurants, and returns ranked recommendations.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: SearchAgent (system agent)

### Preconditions
- User has access to the GoodFoods application
- Database contains restaurant information
- SearchAgent is available and operational

### Postconditions
- User receives a list of restaurant recommendations matching their criteria
- Search results are stored in conversation context for follow-up actions

### Main Flow
1. User enters a search query (e.g., "Find romantic Italian restaurants downtown under $100")
2. ClientAgent receives the message
3. ClientAgent uses LLM to determine intent: "find_restaurants"
4. ClientAgent extracts parameters: cuisine="Italian", ambiance="Romantic", location="Downtown", price_range≤2
5. ClientAgent creates Task for SearchAgent
6. SearchAgent queries database with filters
7. SearchAgent ranks results by relevance (rating, price match, filter alignment)
8. SearchAgent returns Artifact with restaurant list
9. ClientAgent generates natural language response
10. User sees formatted list of recommendations

### Alternative Flows

**A1: No Results Found**
- 6a. SearchAgent finds no matching restaurants
- 6b. SearchAgent returns empty list
- 6c. ClientAgent generates helpful message suggesting alternative search criteria
- 6d. Use case ends

**A2: Ambiguous Query**
- 3a. LLM cannot determine clear intent
- 3b. ClientAgent asks clarifying questions
- 3c. User provides additional information
- 3d. Flow continues from step 3

### Exception Flows

**E1: Database Error**
- 6a. Database query fails
- 6b. SearchAgent returns failure Artifact
- 6c. ClientAgent generates error message
- 6d. Use case ends with error

**E2: LLM API Failure**
- 3a. Groq API call fails
- 3b. System falls back to keyword-based detection
- 3c. Flow continues with reduced accuracy

### Business Rules
- Search results limited to 10 restaurants
- Results ranked by relevance score (rating 40%, price match 20%, ambiance match 20%, location match 20%)
- Price range is 1-4 scale (1=budget, 4=upscale)

### Success Criteria
- User receives relevant results within 2 seconds
- Results match user's stated criteria
- User can proceed to booking from search results

---

## Use Case 2: Restaurant Reservation Creation

**Use Case ID**: UC-002  
**Use Case Name**: Restaurant Reservation Creation  
**Priority**: High  
**Status**: Implemented

### Description
Users can create a restaurant reservation by referencing a search result or specifying restaurant details. The system validates availability, checks capacity, and confirms the booking.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: BookingAgent (system agent), SearchAgent (if search needed)

### Preconditions
- User has identified a restaurant (from search or direct reference)
- Restaurant exists in database
- BookingAgent is available and operational

### Main Flow
1. User requests booking (e.g., "Book the first one for 7pm" or "Reserve a table at Luigi's for 4 people")
2. ClientAgent receives message
3. ClientAgent uses LLM to determine intent: "create_booking"
4. ClientAgent extracts parameters: restaurant_id, party_size, booking_time, user_name
5. ClientAgent resolves context references (e.g., "first one" → restaurant_id from last search)
6. ClientAgent creates Task for BookingAgent
7. BookingAgent validates restaurant exists
8. BookingAgent checks capacity (party_size ≤ restaurant capacity)
9. BookingAgent checks for time slot conflicts
10. BookingAgent creates booking record
11. BookingAgent returns confirmation Artifact
12. ClientAgent generates natural language confirmation
13. User sees booking confirmation with details

### Alternative Flows

**A1: Context Reference (e.g., "the first one")**
- 5a. ClientAgent looks up last_search_results
- 5b. ClientAgent maps "first one" to restaurant_id
- 5c. Flow continues from step 6

**A2: Missing Required Information**
- 4a. LLM cannot extract all required parameters
- 4b. ClientAgent asks for missing information (party_size, time, etc.)
- 4c. User provides information
- 4d. Flow continues from step 4

**A3: Restaurant Not Found**
- 7a. BookingAgent cannot find restaurant
- 7b. BookingAgent returns failure Artifact
- 7c. ClientAgent asks user to clarify restaurant selection
- 7d. Use case ends

### Exception Flows

**E1: Capacity Exceeded**
- 8a. Party size exceeds restaurant capacity
- 8b. BookingAgent returns failure with error message
- 8c. ClientAgent informs user and suggests alternative
- 8d. Use case ends

**E2: Time Slot Already Booked**
- 9a. Time slot conflict detected
- 9b. BookingAgent returns failure with error message
- 9c. ClientAgent suggests alternative times
- 9d. Use case ends

**E3: Invalid Time Format**
- 4a. Booking time cannot be parsed
- 4b. ClientAgent asks user to clarify time
- 4c. Use case continues

**E4: Past Booking Time**
- 8a. BookingAgent detects booking time is in the past
- 8b. BookingAgent returns failure
- 8c. ClientAgent informs user
- 8d. Use case ends

### Business Rules
- Bookings can be made up to 1 year in advance
- Cannot book tables in the past
- Party size must be between 1 and 50
- Time slot conflicts prevent double-booking
- Default user_name is "Guest" if not provided

### Success Criteria
- Booking created successfully
- User receives confirmation with booking ID
- Booking appears in database with correct details

---

## Use Case 3: Reservation Modification

**Use Case ID**: UC-003  
**Use Case Name**: Reservation Modification  
**Priority**: Medium  
**Status**: Implemented

### Description
Users can modify existing reservations (change time, party size) using natural language. The system identifies the booking from context, validates the change, and updates the record.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: BookingAgent (system agent)

### Preconditions
- User has an existing confirmed booking
- Booking ID is known or can be inferred from context
- BookingAgent is available and operational

### Main Flow
1. User requests modification (e.g., "Change my reservation to 8pm" or "Move dinner to 8pm")
2. ClientAgent receives message
3. ClientAgent uses LLM to determine intent: "modify_booking"
4. ClientAgent extracts parameters: booking_id (from context), new_time or new_party_size
5. ClientAgent resolves booking_id from conversation context (last_booking_id)
6. ClientAgent creates Task for BookingAgent
7. BookingAgent retrieves existing booking
8. BookingAgent validates booking exists and is not cancelled
9. BookingAgent validates new time/party_size
10. BookingAgent checks for conflicts with new time
11. BookingAgent updates booking record
12. BookingAgent returns confirmation Artifact
13. ClientAgent generates natural language confirmation
14. User sees modification confirmation

### Alternative Flows

**A1: Booking ID Not in Context**
- 5a. No booking_id found in context
- 5b. ClientAgent asks user for booking ID or restaurant name
- 5c. User provides information
- 5d. Flow continues

**A2: Change Party Size**
- 4a. User requests party size change instead of time
- 4b. BookingAgent validates new party_size against capacity
- 4c. Flow continues from step 9

**A3: Multiple Modifications**
- 4a. User requests both time and party_size change
- 4b. BookingAgent validates both
- 4c. BookingAgent updates both fields
- 4d. Flow continues

### Exception Flows

**E1: Booking Not Found**
- 7a. BookingAgent cannot find booking
- 7b. BookingAgent returns failure
- 7c. ClientAgent asks user to verify booking ID
- 7d. Use case ends

**E2: Booking Already Cancelled**
- 8a. Booking status is "cancelled"
- 8b. BookingAgent returns failure
- 7c. ClientAgent informs user
- 7d. Use case ends

**E3: New Time Conflict**
- 10a. New time slot already booked
- 10b. BookingAgent returns failure
- 10c. ClientAgent suggests alternative times
- 10d. Use case ends

**E4: Invalid Party Size**
- 9a. New party_size exceeds capacity
- 9b. BookingAgent returns failure
- 9c. ClientAgent informs user
- 9d. Use case ends

### Business Rules
- Only confirmed bookings can be modified
- New time must be in the future
- New party_size must not exceed restaurant capacity
- Modification creates audit trail

### Success Criteria
- Booking updated successfully
- User receives confirmation with updated details
- Database reflects changes accurately

---

## Use Case 4: Reservation Cancellation

**Use Case ID**: UC-004  
**Use Case Name**: Reservation Cancellation  
**Priority**: Medium  
**Status**: Implemented

### Description
Users can cancel existing reservations. The system identifies the booking and updates its status to "cancelled".

### Actors
- **Primary**: Customer (end user)
- **Secondary**: BookingAgent (system agent)

### Preconditions
- User has an existing booking
- Booking ID is known or can be inferred from context

### Main Flow
1. User requests cancellation (e.g., "Cancel my reservation" or "I need to cancel")
2. ClientAgent receives message
3. ClientAgent uses LLM to determine intent: "cancel_booking"
4. ClientAgent extracts booking_id from context
5. ClientAgent creates Task for BookingAgent
6. BookingAgent retrieves booking
7. BookingAgent validates booking exists and is not already cancelled
8. BookingAgent updates status to "cancelled"
9. BookingAgent returns confirmation Artifact
10. ClientAgent generates natural language confirmation
11. User sees cancellation confirmation

### Exception Flows

**E1: Booking Not Found**
- 6a. BookingAgent cannot find booking
- 6b. BookingAgent returns failure
- 6c. ClientAgent asks user to verify booking ID
- 6d. Use case ends

**E2: Already Cancelled**
- 7a. Booking status is already "cancelled"
- 7b. BookingAgent returns failure
- 7c. ClientAgent informs user
- 7d. Use case ends

### Business Rules
- Cancelled bookings cannot be modified
- Cancellation is permanent (no undo)
- Cancelled bookings free up time slots for other customers

### Success Criteria
- Booking status updated to "cancelled"
- User receives confirmation
- Time slot becomes available for other bookings

---

## Use Case 5: Complex Multi-Constraint Search

**Use Case ID**: UC-005  
**Use Case Name**: Complex Multi-Constraint Search  
**Priority**: Medium  
**Status**: Implemented

### Description
Users can search with multiple complex constraints including budget calculations, special occasions, and specific requirements. The system intelligently parses all constraints and returns highly relevant results.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: SearchAgent (system agent)

### Preconditions
- User has access to the application
- Database contains restaurants with diverse attributes

### Main Flow
1. User enters complex query (e.g., "Anniversary dinner, romantic ambiance, Italian food, under $200 for two")
2. ClientAgent receives message
3. ClientAgent uses LLM to parse all constraints:
   - Occasion: Anniversary
   - Ambiance: Romantic
   - Cuisine: Italian
   - Budget: $200 total for 2 people = $100 per person
4. ClientAgent calculates price_range from budget (price_per_person → price_range mapping)
5. ClientAgent creates Task for SearchAgent with all filters
6. SearchAgent queries database with multiple filters
7. SearchAgent ranks results considering all constraints
8. SearchAgent returns top-ranked results
9. ClientAgent generates natural language response highlighting matches
10. User sees curated recommendations

### Alternative Flows

**A1: Budget Per Person vs Total**
- 3a. User specifies "under $50 per person"
- 3b. ClientAgent maps directly to price_range
- 3c. Flow continues

**A2: Ambiguous Constraints**
- 3a. LLM cannot parse all constraints
- 3b. ClientAgent asks clarifying questions
- 3c. User provides additional information
- 3d. Flow continues

### Exception Flows

**E1: No Matching Results**
- 6a. No restaurants match all constraints
- 6b. SearchAgent returns empty list
- 6c. ClientAgent suggests relaxing constraints
- 6d. Use case ends

### Business Rules
- Budget calculations: $1-25/person = price_range 1, $26-50 = 2, $51-100 = 3, $100+ = 4
- Results ranked by multi-factor relevance score
- Maximum 10 results returned

### Success Criteria
- All constraints are correctly interpreted
- Results match all specified criteria
- User receives helpful recommendations

---

## Use Case 6: Context-Aware Follow-up Queries

**Use Case ID**: UC-006  
**Use Case Name**: Context-Aware Follow-up Queries  
**Priority**: Low  
**Status**: Implemented

### Description
Users can ask follow-up questions about previous search results or bookings without restating context. The system maintains conversation context and resolves references.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: ClientAgent (context management)

### Preconditions
- User has previous interaction in the conversation
- Conversation context is maintained

### Main Flow
1. User asks follow-up (e.g., "What's the rating of the second one?" or "Tell me more about that Italian place")
2. ClientAgent receives message
3. ClientAgent retrieves conversation context (last_search_results)
4. ClientAgent resolves reference ("second one" → restaurant_id from results[1])
5. ClientAgent queries database for additional details
6. ClientAgent generates response with requested information
7. User sees detailed information

### Alternative Flows

**A1: Reference to Previous Booking**
- 3a. User asks about their booking
- 3b. ClientAgent retrieves last_booking_id from context
- 3c. ClientAgent queries booking details
- 3d. Flow continues

**A2: Ambiguous Reference**
- 4a. ClientAgent cannot resolve reference
- 4b. ClientAgent asks user to clarify
- 4c. Use case continues

### Business Rules
- Context maintained for current session only
- References resolved using last_search_results or last_booking_id
- Context cleared on conversation reset

### Success Criteria
- References correctly resolved
- User receives requested information
- Context maintained across multiple turns

---

## Use Case 7: Error Recovery and Clarification

**Use Case ID**: UC-007  
**Use Case Name**: Error Recovery and Clarification  
**Priority**: Medium  
**Status**: Implemented

### Description
When the system encounters errors or ambiguous queries, it gracefully handles the situation by asking clarifying questions or providing helpful error messages, allowing users to recover and continue.

### Actors
- **Primary**: Customer (end user)
- **Secondary**: All agents (error handling)

### Preconditions
- User interaction in progress
- Error condition encountered

### Main Flow
1. User enters query that causes error or ambiguity
2. System encounters error (e.g., missing parameter, invalid format, not found)
3. Agent returns failure Artifact with error message
4. ClientAgent receives failure
5. ClientAgent generates user-friendly error message
6. ClientAgent suggests corrective action or asks clarifying question
7. User sees helpful error message
8. User provides corrected information or clarification
9. System retries operation
10. Operation succeeds

### Alternative Flows

**A1: LLM API Failure**
- 2a. Groq API call fails
- 2b. System falls back to keyword-based detection
- 2c. Flow continues with reduced functionality

**A2: Database Error**
- 2a. Database query fails
- 2b. Agent returns failure
- 2c. ClientAgent informs user and suggests retry
- 2d. Use case ends

**A3: Validation Error**
- 2a. User input fails validation (e.g., invalid time format)
- 2b. Agent returns failure with specific error
- 2c. ClientAgent explains error and shows correct format
- 2d. User corrects input
- 2e. Flow continues

### Business Rules
- All errors return user-friendly messages
- System always provides path forward (suggestion or clarification)
- No technical error messages exposed to users
- Fallback mechanisms available for critical failures

### Success Criteria
- User understands what went wrong
- User knows how to fix the issue
- System recovers gracefully
- User can complete their original intent

---

## Summary

These use cases demonstrate the comprehensive functionality of the GoodFoods AI Reservation System, covering:

1. **Discovery**: Smart search with multiple constraints
2. **Booking**: Seamless reservation creation
3. **Modification**: Easy updates to existing bookings
4. **Cancellation**: Simple cancellation process
5. **Complex Queries**: Handling sophisticated search requirements
6. **Context Management**: Maintaining conversation context
7. **Error Handling**: Graceful error recovery

All use cases follow the A2A architecture pattern, with ClientAgent orchestrating and specialist agents (SearchAgent, BookingAgent) performing specific tasks.

