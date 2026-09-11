import sys
from src.chatbot import HybridChatbot


def print_banner():
    print("=" * 65)
    print("   🤖 Hybrid Rule-Based & NLP Chatbot with SQL Storage")
    print("=" * 65)
    print(" Commands:")
    print("  • /debug    - Toggle debug info (intent, confidence, method, slots)")
    print("  • /bookings - List all bookings stored in SQLite database")
    print("  • /logs     - View recent chat audit logs from SQL database")
    print("  • /status   - View current session slots & active booking")
    print("  • /reset    - Clear current conversation state")
    print("  • quit/bye  - Exit chatbot")
    print(" Try asking:")
    print("  - 'What are your hours?'")
    print("  - 'Book a table for 4 tomorrow at 7pm'")
    print("  - 'How much does consultation cost?'")
    print("=" * 65 + "\n")


def main():
    print("Initializing NLP pipeline, ML intent classifier & SQLite database...")
    bot = HybridChatbot()
    print_banner()

    debug_mode = False
    session_id = "cli_user"

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["quit", "exit", "bye", "goodbye"]:
            res = bot.respond(user_input, session_id=session_id)
            print(f"Bot: {res['response']}")
            print("Session ended. Goodbye!")
            break

        if user_input.lower() == "/debug":
            debug_mode = not debug_mode
            status = "ON" if debug_mode else "OFF"
            print(f"⚙️  Debug Mode is now: {status}\n")
            continue

        if user_input.lower() == "/bookings":
            bookings = bot.db.list_all_bookings(limit=10)
            print("\n🗄️  Recent Bookings in SQL Database:")
            if not bookings:
                print(" (No bookings recorded yet)")
            for b in bookings:
                print(f" • [{b['status']}] ID: {b['booking_id']} | Name: {b['customer_name']} | Service: {b['service']} | Party: {b['party_size']} | {b['booking_date']} at {b['booking_time']}")
            print()
            continue

        if user_input.lower() == "/logs":
            logs = bot.db.get_session_logs(session_id, limit=5)
            print("\n📝 Recent Chat Logs in SQL Database:")
            if not logs:
                print(" (No logs recorded yet)")
            for l in logs:
                print(f" • Turn #{l['log_id']} | [{l['intent']} / {l['method']}] User: '{l['user_message']}' -> Bot: '{l['bot_response'][:40]}...'")
            print()
            continue

        if user_input.lower() == "/status":
            state = bot.get_or_create_state(session_id)
            print("\n📊 Current Session State:")
            print(f" • Active Intent: {state.active_intent}")
            print(f" • Pending Slot:  {state.pending_slot}")
            print(f" • Current Slots: {state.slots}")
            print(f" • Active Booking: {state.active_booking}\n")
            continue

        res = bot.respond(user_input, session_id=session_id)

        print(f"\nBot: {res['response']}\n")

        if debug_mode:
            print("┌" + "─" * 50 + "┐")
            print(f"│ 🎯 Intent:     {res['intent']:<35} │")
            print(f"│ 🛠️  Method:     {res['method']:<35} │")
            print(f"│ 📈 Confidence: {res['confidence']:<35.2f} │")
            if res.get('slots'):
                print(f"│ 🧩 Slots:      {str(res['slots']):<35} │")
            if res.get('pending_slot'):
                print(f"│ ⏳ Pending:    {str(res['pending_slot']):<35} │")
            print("└" + "─" * 50 + "┘\n")


if __name__ == "__main__":
    main()
