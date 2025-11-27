from backend.agents.client_agent import ClientAgent

def test_scenarios():
    client = ClientAgent()

    print("--- Scenario 1: Search ---")
    user_input = "Find me a romantic Italian restaurant downtown under $100"
    print(f"User: {user_input}")
    response = client.process_message(user_input)
    print(f"Agent: {response}\n")

    print("--- Scenario 2: Booking ---")
    user_input = "Book the second one for 7 pm"
    print(f"User: {user_input}")
    response = client.process_message(user_input)
    print(f"Agent: {response}\n")

    print("--- Scenario 3: Modification ---")
    user_input = "Actually, change it to 8 pm"
    print(f"User: {user_input}")
    response = client.process_message(user_input)
    print(f"Agent: {response}\n")

if __name__ == "__main__":
    test_scenarios()
