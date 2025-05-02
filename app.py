# app.py
from flask import Flask, request, jsonify, render_template
import spacy
import re
import random
import uuid

# --- Load spaCy Model ---
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("SpaCy model 'en_core_web_sm' not found. Downloading...")
    try:
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
        print("Download and load successful.")
    except Exception as e:
        print(f"Error downloading spaCy model: {e}")
        print("Please run 'python -m spacy download en_core_web_sm' manually in your terminal.")
        exit() # Exit if model isn't available


# --- Menu Data ---
# Use canonical IDs (snake_case) internally, map human-readable phrases to them.
# Items with a 'description' are considered purchasable menu items.
MENU = {
    "margherita pizza": {"id": "margherita_pizza", "price": 12.99, "category": "main", "description": "Classic tomato, mozzarella, and basil.", "upsell_suggest": ["garlic_bread", "coke"]},
    "pepperoni pizza": {"id": "pepperoni_pizza", "price": 14.99, "category": "main", "description": "Spicy pepperoni and extra cheese.", "upsell_suggest": ["garlic_bread", "coke"]}, # Using coke consistently
    "burger": {"id": "burger", "price": 11.50, "category": "main", "description": "Juicy beef patty with lettuce, tomato, and our special sauce.", "upsell_suggest": ["fries", "coke", "chocolate_cake"]}, # Upsell cake
    "fries": {"id": "fries", "price": 3.50, "category": "side", "description": "Crispy golden fries.", "upsell_suggest": ["coke"]},
    "garlic bread": {"id": "garlic_bread", "price": 4.50, "category": "side", "description": "Toasted bread with garlic butter.", "upsell_suggest": []}, # No upsell for garlic bread for now
    "coke": {"id": "coke", "price": 2.00, "category": "drink", "description": "Refreshing Coca-Cola.", "upsell_suggest": []},
    "chocolate cake": {"id": "chocolate_cake", "price": 6.00, "category": "dessert", "description": "Rich, decadent chocolate cake.", "upsell_suggest": []},
    "water": {"id": "water", "price": 1.50, "category": "drink", "description": "Bottled water.", "upsell_suggest": []},
    # --- Add synonyms/variations mapping to canonical IDs (no description, not purchasable directly) ---
    "pizza": {"id": "pizza_generic"}, # Generic pizza term
    "burgers": {"id": "burger"}, # Plural maps to singular ID
    "french fries": {"id": "fries"},
    "cola": {"id": "coke"},
    "cake": {"id": "chocolate_cake"}, # Generic cake maps to specific type
    "margherita": {"id": "margherita_pizza"}, # Can say just "margherita"
    "pepperoni": {"id": "pepperoni_pizza"}, # Can say just "pepperoni"
}

# Helper to get item details by canonical ID
def get_item_details_by_id(item_id):
    """Finds the MENU entry for a given canonical ID."""
    for item_key, details in MENU.items():
        if details.get("id") == item_id and "description" in details: # Ensure it's a purchasable item
            return details # Return the details dictionary

    # Also check if the ID itself is a key for some reason (shouldn't happen with above structure but safe)
    if item_id in MENU and "description" in MENU[item_id]:
         return MENU[item_id]

    return None # Not found or not a purchasable item

# Helper to get display name by canonical ID
def get_display_name_by_id(item_id):
     """Finds a human-readable display name for a given canonical ID."""
     # Prioritize finding the original key from a purchasable item entry
     for item_key, details in MENU.items():
         if details.get("id") == item_id and "description" in details:
             # Capitalize each word of the original key
             return " ".join(word.capitalize() for word in item_key.split(' '))

     # Fallback: if not found in purchasable items, maybe it's a synonym ID?
     # Or just use the ID itself, replacing underscores with spaces and capitalizing
     return " ".join(word.capitalize() for word in item_id.replace('_', ' ').split(' '))


# --- Chatbot Personality Phrases ---
PERSONALITY = {
    "welcome": [
        "Hey there! Ready to order some deliciousness?",
        "Hi! What can I get cookin' for you today?",
        "Hello! Hungry? I'm ready to take your order!",
        "Welcome! Let's get your food journey started!"
    ],
    "item_added": [
        "Got it! One {item_name} added to your order! 🎉",
        "Excellent choice! Adding the {item_name} to your basket.",
        "Yum! {item_name} on its way to your cart! 😋",
        "Alright, one {item_name} secured!"
    ],
     "item_quantity_added": [
        "Got it! {quantity}x {item_name} added!",
        "Adding {quantity} of the delicious {item_name} for you!"
     ],
    "item_not_found": [
        "Hmm, I don't see '{item_name}' on our menu right now. Was it something else?",
        "My apologies, I didn't quite catch that item. We don't seem to have '{item_name}'. You can ask me to 'show menu'!",
        "Are you sure about '{item_name}'? You can type 'menu' to see our current offerings!"
    ],
     "clarify_item_needed": {
         "pizza_generic": ["We have a few pizzas! Did you mean the Margherita or the Pepperoni?", "Which pizza are you craving? Margherita or Pepperoni?"],
         # Add other generic items if needed
     },
    "ask_something_else": [
        "Anything else catching your eye?",
        "What else can I add for you?",
        "Still browsing, or shall we move on?",
        "Need anything else to complete your feast?",
        "What's next on your craving list?"
    ],
    "upsell_suggestions": [
        "Ooh, the {upsell_item} goes *perfectly* with that! Chefs kiss! 😉",
        "Thinking about a little something extra? How about {upsell_item}?",
        "Pro tip: Many folks love adding {upsell_item} when they get the {main_item}!",
        "To make that {main_item} even better, you HAVE to try it with {upsell_item}!"
    ],
     "recommendations": [
         "Feeling adventurous? How about our {item_name}?",
         "If you like that, you might love our {item_name}!",
         "Can't decide? Our {item_name} is a crowd favorite!"
     ],
     "checkout": [
        "Okay, summing up your order!",
        "Ready to checkout? Here's what you've got:",
        "Looks like you're ready! Let's review your order:"
    ],
    "empty_order": [
        "Your order is currently empty!",
        "Nothing in the basket yet! Let's add something yummy."
    ],
    "goodbye": [
        "Thanks for ordering! Your food will be ready soon!",
        "Enjoy your meal! See you next time!",
        "Order placed! Get ready for some tasty eats!",
        "Happy dining! Come back soon!"
    ],
    "clarify": [
        "Sorry, I didn't quite get that. Could you rephrase?",
        "My AI brain is a little fuzzy on that one. Can you clarify?",
        "Could you explain what you mean by that?",
        "I'm not sure I understood. Could you try saying that differently?"
    ]
}

# --- Helper function to get a random choice from an array ---
def random_choice(arr):
    return random.choice(arr)

# --- Helper to format the order summary string ---
def format_order_summary(order_state):
    items_in_order = {k:v for k, v in order_state["items"].items() if v > 0}

    if not items_in_order:
        return random_choice(PERSONALITY["empty_order"])

    summary = random_choice(PERSONALITY["checkout"]) + "\n"
    total = 0
    for item_id, quantity in items_in_order.items():
        item_details = get_item_details_by_id(item_id)
        if item_details:
            display_name = get_display_name_by_id(item_id)
            price = item_details.get("price", 0)
            summary += f"- {quantity}x {display_name} ({price:.2f}$ each)\n"
            total += quantity * price
        else:
            # Fallback for items in order state that don't map to purchasable items (error state)
            display_name = get_display_name_by_id(item_id) # Try to get a display name anyway
            summary += f"- {quantity}x {display_name} (Price Unknown/Error)\n" # Indicate error

    summary += f"\nTotal: {total:.2f}$"
    return summary


# --- Helper to find menu item in text using spaCy and string matching ---
def find_menu_item(doc, menu_dict):
    """Searches spaCy Doc and text for menu items, prioritizing longer matches and mapping to canonical IDs."""
    lower_text = doc.text.lower()
    found_phrase = None # The exact phrase matched in the text
    canonical_id = None # The canonical ID from the MENU data
    match_char_index = -1 # Character index of the start of the match

    # Create a list of all potential phrases to match (menu keys + canonical IDs with underscores replaced)
    # Sort by length descending to match "margherita pizza" before just "pizza"
    # Using a set comprehension for efficiency and uniqueness
    potential_phrases = sorted(
        list(menu_dict.keys()) + [v.get("id", "").replace('_', ' ') for v in menu_dict.values() if v.get("id")],
        key=len,
        reverse=True
    )

    for phrase in potential_phrases:
        if not phrase: continue # Skip empty phrases just in case

        current_match_index = lower_text.find(phrase.lower()) # Find case-insensitive
        if current_match_index != -1:
            found_phrase = phrase.lower()
            match_char_index = current_match_index

            # Find the corresponding canonical ID for the matched phrase
            canonical_id_found = None
            # Check original keys first
            if found_phrase in menu_dict:
                 canonical_id_found = menu_dict[found_phrase].get("id", found_phrase.replace(' ', '_'))
            # Check if the phrase (with underscores) matches an ID
            elif found_phrase.replace(' ', '_') in [v.get("id") for v in menu_dict.values()]:
                 canonical_id_found = found_phrase.replace(' ', '_')
            # Fallback: Iterate through values to find match by ID or key (less efficient but covers edge cases)
            else:
                for key, value in menu_dict.items():
                    if key.lower() == found_phrase or value.get("id", "").lower() == found_phrase.replace(' ', '_'):
                         canonical_id_found = value.get("id", key.lower().replace(' ', '_'))
                         break # Found the canonical mapping

            canonical_id = canonical_id_found if canonical_id_found else found_phrase.replace(' ', '_') # Default if not found explicitly


            break # Found the longest match, stop searching

    # print(f"Debug: find_menu_item found phrase '{found_phrase}' mapped to canonical ID '{canonical_id}' at index {match_char_index}") # Debugging
    return found_phrase, canonical_id, match_char_index


# --- Helper to extract quantity near an index in a spaCy Doc ---
def extract_quantity(doc, item_char_index):
    """Looks for numbers or number words near the found item's character index."""
    quantity = 1 # Default quantity
    lower_text = doc.text.lower()

    # Find the token index corresponding to the character index (start of the item phrase)
    item_token_index = -1
    # Iterate through tokens to find the one whose start index matches or is just before item_char_index
    for i, token in enumerate(doc):
        if token.idx >= item_char_index:
            item_token_index = i
            # If the item phrase spans multiple tokens, find the last token's index too
            # Simple approach: assume item phrase corresponds to consecutive tokens
            # Need a better way to find the *end* token index of the matched phrase
            item_phrase_len = len(doc.text[item_char_index:]) # Remaining text length from match start - potentially too long
            # Let's refine this: find the token that *contains* the end of the matched phrase
            found_phrase, _, _ = find_menu_item(doc, MENU) # Re-find the phrase to get its actual length
            if found_phrase:
                 item_phrase_length = len(found_phrase)
                 item_end_char_index = item_char_index + item_phrase_length
                 item_token_end_index = item_token_index # Start from the beginning token
                 while item_token_end_index + 1 < len(doc) and doc[item_token_end_index + 1].idx < item_end_char_index:
                      item_token_end_index += 1
            else:
                 item_token_end_index = item_token_index # Default to single token if phrase not re-found

            break


    if item_token_index == -1:
         # Should not happen if item_char_index is valid
         print(f"Debug: Could not map item char index {item_char_index} to token index.")
         return quantity

    # Define a window around the item tokens
    search_window_start = max(0, item_token_index - 4) # Look up to 4 tokens before
    # Use item_token_end_index + 3 to look a few tokens after the *end* token
    search_window_end = min(len(doc), item_token_end_index + 3)


    # Check tokens in the window for numbers or number words
    # Prioritize tokens *before* the item tokens
    for i in range(search_window_start, item_token_index):
        token = doc[i]
        # print(f"Debug: Checking token '{token.text}' (index {i}) for quantity before item (start index {item_token_index}).") # Debugging
        if token.like_num:
            try:
                # Check if it's a digit (e.g., "3")
                quantity = int(token.text)
                # print(f"Debug: Found digit quantity '{quantity}' before item.") # Debugging
                return quantity
            except ValueError:
                # Handle common number words not caught by int()
                if token.text.lower() == "one": quantity = 1; # print("Debug: Found word quantity 'one' before item.");
                elif token.text.lower() == "two": quantity = 2; # print("Debug: Found word quantity 'two' before item.");
                elif token.text.lower() == "three": quantity = 3; # print("Debug: Found word quantity 'three' before item.");
                # Add more number words as needed
                if quantity != 1: return quantity # Return if a word quantity was found


    # If not found before, search tokens *after* the item (less common, e.g., "burger two")
    # Start checking from the token where the item phrase ends + 1
    start_after_item = item_token_end_index + 1
    for i in range(start_after_item, search_window_end):
        token = doc[i]
        # print(f"Debug: Checking token '{token.text}' (index {i}) for quantity after item (end index {item_token_end_index}).") # Debugging
        if token.like_num:
            try:
                quantity = int(token.text)
                 # print(f"Debug: Found digit quantity '{quantity}' after item.") # Debugging
                return quantity
            except ValueError:
                if token.text.lower() == "one": quantity = 1; # print("Debug: Found word quantity 'one' after item.");
                elif token.text.lower() == "two": quantity = 2; # print("Debug: Found word quantity 'two' after item.");
                elif token.text.lower() == "three": quantity = 3; # print("Debug: Found word quantity 'three' after item.");
                 # Add more number words as needed
                if quantity != 1: return quantity # Return if a word quantity was found

    # print(f"Debug: No quantity found in window, defaulting to {quantity}") # Debugging
    return quantity


# --- Main NLU Parsing Function ---
# FIX: Added order_state as an argument
def parse_user_input_nlp(user_text, order_state):
    """
    Parses user text using spaCy and rule-based methods to determine intent and extract entities.
    order_state is passed for state-dependent intent parsing (like 'confirm' during checkout).
    """
    doc = nlp(user_text)
    lower_text = user_text.lower().strip()

    parsed_data = {"intent": "unknown", "entities": {}}

    print(f"Debug: Parsing input: '{user_text}' in state: '{order_state['status']}'") # Debugging start of parse

    # --- State-Dependent Intent Recognition ---
    # Highest priority: Handle confirmations/cancellations during checkout
    if order_state["status"] == "checkout":
        # Look for confirmation words (lemmas) potentially near order/checkout words
        if (any(token.lemma_ in ["confirm", "yes", "place", "go", "ok", "submit"] for token in doc) and # Added "submit", "ok"
            any(token.text.lower() in ["order", "it", "checkout", "please", "yes", "ok", "go"] for token in doc)): # Added "go", "ok"
             parsed_data["intent"] = "confirm_checkout"
        # Look for cancellation words (lemmas)
        elif any(token.lemma_ in ["cancel", "no", "wait", "hold", "stop", "nevermind"] for token in doc): # Added "nevermind"
             parsed_data["intent"] = "cancel_checkout"

        # If one of the state-dependent intents was found, return immediately
        if parsed_data["intent"] != "unknown":
             print(f"Debug: State-dependent intent '{parsed_data['intent']}' found in checkout state.")
             return parsed_data

    # Priority 2: Handle responses when waiting for clarification (e.g., pizza type)
    if order_state["status"] == "waiting_for_clarification":
        # Try to find a specific item that clarifies the previous generic one
        found_phrase, canonical_id, item_char_index = find_menu_item(doc, MENU)
        item_id_being_clarified = order_state.get("clarifying_item_id")

        if item_id_being_clarified == "pizza_generic":
            if canonical_id in ["margherita_pizza", "pepperoni_pizza"]:
                # Found a specific pizza, assume this is the clarification response
                 parsed_data["intent"] = "add_item" # Change intent to add this specific item
                 parsed_data["entities"]["item_name"] = canonical_id
                 # Try to extract quantity again, defaulting to 1
                 parsed_data["entities"]["quantity"] = extract_quantity(doc, item_char_index) if found_phrase else 1
                 print(f"Debug: Found specific item '{canonical_id}' clarifying pizza.")
                 return parsed_data # Return immediately with the add_item intent
            # If they said something else but it was a menu item (e.g. "Actually, get a burger"), process that instead
            elif canonical_id and canonical_id != item_id_being_clarified: # Found a *different* valid item
                 parsed_data["intent"] = "add_item"
                 parsed_data["entities"]["item_name"] = canonical_id
                 parsed_data["entities"]["quantity"] = extract_quantity(doc, item_char_index) if found_phrase else 1
                 print(f"Debug: Found different item '{canonical_id}' while waiting for '{item_id_being_clarified}' clarification.")
                 return parsed_data # Process adding the new item

        # Add logic for other clarifying items if needed
        # elif item_id_being_clarified == "some_other_generic_id":
        #    ... handle specific item responses for that generic type ...


        # If in clarification state and didn't find a specific item that clarifies,
        # let it fall through to general intents or unknown.


    # Priority 3: General Intent Recognition (Keyword/Phrase Matching using lemmas)
    # Using token.lemma_ makes it match base forms (e.g., "greeting" -> "greet")
    if any(token.lemma_ in ["hello", "hi", "hey", "greeting"] for token in doc):
        parsed_data["intent"] = "greet"
    elif any(token.lemma_ in ["menu", "option", "show", "list", "items"] for token in doc) and any(token.text.lower() in ["menu", "options", "list", "items"] for token in doc): # Added "items" to text match
         parsed_data["intent"] = "show_menu"
    elif any(token.lemma_ in ["checkout", "finish", "done", "pay", "ready", "complete"] for token in doc): # Added "complete"
         parsed_data["intent"] = "start_checkout"
    elif any(token.lemma_ in ["order", "basket", "got", "item", "show", "summary"] for token in doc) and any(token.text.lower() in ["order", "basket", "items", "summary"] for token in doc): # Added "summary"
         parsed_data["intent"] = "show_order"
    elif any(token.lemma_ in ["recommend", "suggest", "what", "try"] for token in doc) and any(token.text.lower() in ["recommend", "suggest", "try"] for token in doc):
         parsed_data["intent"] = "recommend"
    elif any(token.lemma_ in ["bye", "exit", "quit", "leave"] for token in doc):
         parsed_data["intent"] = "goodbye"
    # Add more general intents like "ask_question", "thank_you" if needed

    # Priority 4: Entity Extraction & Add Item Intent
    # If no explicit command intent found yet (or if it's just a greet/unknown in non-clarification state), check if the user is asking for an item
    if parsed_data["intent"] == "unknown" or parsed_data["intent"] == "greet" or order_state["status"] == "waiting_for_clarification":
        # Even if in clarification state, if the input didn't clarify, it might be a new item or an unknown input
        found_phrase, canonical_id, item_char_index = find_menu_item(doc, MENU)

        if found_phrase and canonical_id:
            # Found a menu item phrase or a phrase mapping to one
            # Check if the found item is one we know needs clarification *and* we weren't already clarifying it
            # This prevents asking "Which pizza?" repeatedly if they just type "pizza" again
            is_generic_that_needs_clarification = canonical_id in PERSONALITY["clarify_item_needed"]
            was_already_clarifying_this_generic = order_state.get("clarifying_item_id") == canonical_id

            if is_generic_that_needs_clarification and not was_already_clarifying_this_generic:
                parsed_data["intent"] = "clarify_item"
                parsed_data["entities"]["item_id"] = canonical_id # Store the generic ID that needs clarification
                parsed_data["entities"]["original_phrase"] = found_phrase # Keep original text if needed
            else:
                 # Found a specific, purchasable item ID OR found a generic we were *already* clarifying (treat as unknown/clarify again)
                 # Check if it's a purchasable item
                 if get_item_details_by_id(canonical_id):
                     parsed_data["intent"] = "add_item"
                     parsed_data["entities"]["item_name"] = canonical_id # Store the canonical ID
                     parsed_data["entities"]["quantity"] = extract_quantity(doc, item_char_index) if found_phrase else 1
                 elif was_already_clarifying_this_generic:
                      # If they just repeated the generic term while we were clarifying, treat as unknown or re-prompt clarification
                      parsed_data["intent"] = "unknown" # Let the unknown handler give the clarification prompt again or a general one
                      print(f"Debug: Repeated generic item '{canonical_id}' while clarifying.")
                 else:
                      # Found a term that's in MENU but not a purchasable item (like a typo or unrelated word matching a synonym)
                      parsed_data["intent"] = "unknown" # Treat as unknown


    print(f"Debug: Parsed Data: {parsed_data}")
    return parsed_data

# --- Dialog Management & Response Generation ---
# This function takes the parsed input, updates the state, and generates the bot's response.
# This is where the "Agentic" behavior and "Fun" personality come in.
def generate_bot_response(parsed_input, order_state):
    """
    Processes parsed user input, updates order state, and generates bot response.
    order_state is a dictionary passed by reference (mutable).
    """
    intent = parsed_input["intent"]
    entities = parsed_input.get("entities", {})
    # Default response is handled at the end if no intent matches or is unknown
    response_text = None

    print(f"Debug: Generating response for intent: '{intent}' from state: '{order_state['status']}'")

    # --- State Transition and Logic based on Intent ---
    if intent == "greet":
        response_text = random_choice(PERSONALITY["welcome"])
        order_state["status"] = "browsing" # Ensure status is appropriate
        # Clear clarification state if greeting in middle of flow
        if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"]


    elif intent == "show_menu":
        response_text = "Okay, here's what we're serving up:\n"
        # Filter for purchasable items (have a description) and sort by category, then name
        purchasable_items = [(k, v) for k, v in MENU.items() if "description" in v]
        sorted_menu_items = sorted(purchasable_items, key=lambda item: (item[1].get("category", ""), item[0]))

        for item_key, details in sorted_menu_items:
             display_name = " ".join(word.capitalize() for word in item_key.split(' '))
             response_text += f"- {display_name}: {details['price']:.2f}$ - {details['description']}\n"
        response_text += "\n" + random_choice(PERSONALITY["ask_something_else"])
        order_state["status"] = "browsing" # User is browsing the menu
        if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"] # Clear clarification state


    elif intent == "add_item":
        item_id = entities.get("item_name") # This is the canonical ID
        quantity = entities.get("quantity", 1)

        # Find the display name and details using the canonical ID
        item_details = get_item_details_by_id(item_id)
        display_name = get_display_name_by_id(item_id) # Get display name from ID

        if item_details: # Check if it's a valid purchasable item
            # Update state
            if item_id in order_state["items"]:
                order_state["items"][item_id] += quantity
            else:
                order_state["items"][item_id] = quantity
            order_state["last_item_added"] = item_id
            order_state["status"] = "ordering" # User is actively adding items

            # Generate response with personality and item confirmation
            if quantity > 1:
                 response_text = random_choice(PERSONALITY["item_quantity_added"]).format(quantity=quantity, item_name=display_name)
            else:
                 response_text = random_choice(PERSONALITY["item_added"]).format(item_name=display_name)


            # --- Simple Upselling Logic ---
            # Get suggestions using canonical IDs from the item details
            suggested_items_ids = item_details.get("upsell_suggest", [])
            # Filter suggestions: must be a purchasable item, and preferably not already in the order
            potential_suggestions_ids = [
                s_id for s_id in suggested_items_ids
                if get_item_details_by_id(s_id) # Check if the suggested ID maps to a purchasable item
                and s_id not in order_state["items"] # Don't suggest if already in order (simple check)
            ]

            if potential_suggestions_ids:
                suggestion_id = random_choice(potential_suggestions_ids)
                suggestion_display_name = get_display_name_by_id(suggestion_id) # Get display name for suggestion

                response_text += "\n" + random_choice(PERSONALITY["upsell_suggestions"]).format(
                    upsell_item=suggestion_display_name,
                    main_item=display_name
                )

            response_text += "\n" + random_choice(PERSONALITY["ask_something_else"]) # Always ask if they want more

            # If we were waiting for clarification, reset the state now that an item was added
            if order_state["status"] == "waiting_for_clarification":
                 order_state["status"] = "ordering" # Or go back to previous state (ordering is fine here)
                 if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"] # Clear the clarification context


        else:
            # Item name or ID was found by NLU but doesn't map to a valid *purchasable* menu item ID
             response_text = random_choice(PERSONALITY["item_not_found"]).format(item_name=display_name) # Use the display name we found/generated
             # State remains the same or could go back to browsing (let's keep current state)
             # Clear clarification state if this happened while clarifying
             if order_state["status"] == "waiting_for_clarification" and "clarifying_item_id" in order_state:
                  del order_state["clarifying_item_id"]
                  order_state["status"] = "ordering" # Exit clarification state


    elif intent == "clarify_item":
        item_id_to_clarify = entities.get("item_id")

        # Check if we have clarification phrases for this generic ID
        clarification_phrases = PERSONALITY["clarify_item_needed"].get(item_id_to_clarify)

        if clarification_phrases:
            response_text = random_choice(clarification_phrases)
            order_state["status"] = "waiting_for_clarification" # Set a specific state to handle the reply
            order_state["clarifying_item_id"] = item_id_to_clarify # Store which item needs clarifying
        else:
             # Fallback if we don't have specific phrases for this type of clarification
             response_text = random_choice(PERSONALITY["clarify"]) + " Could you be more specific about that?"
             # State remains the same or goes back to browsing
             if order_state["status"] == "waiting_for_clarification" and "clarifying_item_id" in order_state:
                  del order_state["clarifying_item_id"] # Clear if it was set to something unexpected
                  order_state["status"] = "ordering" # Exit clarification state


    elif intent == "show_order":
         items_in_order = {k:v for k, v in order_state["items"].items() if v > 0}
         if not items_in_order:
              response_text = random_choice(PERSONALITY["empty_order"])
         else:
             response_text = format_order_summary(order_state)

         response_text += "\n" + random_choice(PERSONALITY["ask_something_else"])
         order_state["status"] = "ordering" # User is reviewing, still in the ordering flow
         if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"] # Clear clarification state


    elif intent == "recommend":
         # Simple recommendation logic: suggest a main if order empty, dessert/side/drink if mains present
         items_in_order = {k:v for k, v in order_state["items"].items() if v > 0}
         has_main = any(get_item_details_by_id(item_id) and get_item_details_by_id(item_id).get("category") == "main" for item_id in items_in_order)
         has_dessert_or_side = any(get_item_details_by_id(item_id) and get_item_details_by_id(item_id).get("category") in ["side", "drink", "dessert"] for item_id in items_in_order)

         recommendation_pool_ids = []
         # Filter for purchasable items only
         purchasable_item_ids = [v["id"] for v in MENU.values() if "description" in v]

         if not items_in_order:
              # If order is empty, suggest a main dish (canonical IDs of actual items)
              recommendation_pool_ids = [item_id for item_id in purchasable_item_ids if get_item_details_by_id(item_id).get("category") == "main"]
         elif has_main and not has_dessert_or_side:
              # If they have a main but no side/drink/dessert, suggest those
              recommendation_pool_ids = [item_id for item_id in purchasable_item_ids if get_item_details_by_id(item_id).get("category") in ["side", "drink", "dessert"]]
         else:
              # Otherwise, suggest any purchasable item not already in their order
              recommendation_pool_ids = [item_id for item_id in purchasable_item_ids if item_id not in items_in_order]
              # Could add logic to prioritize popular items here


         # Remove duplicates just in case and ensure pool is not empty
         recommendation_pool_ids = list(set(recommendation_pool_ids))

         if recommendation_pool_ids:
              suggested_item_id = random_choice(recommendation_pool_ids)
              # Find display name and description using helpers
              suggested_item_details = get_item_details_by_id(suggested_item_id)
              suggested_display_name = get_display_name_by_id(suggested_item_id)

              response_text = random_choice(PERSONALITY["recommendations"]).format(item_name=suggested_display_name)
              if suggested_item_details and suggested_item_details.get("description"): # Ensure details were found
                  response_text += f" ({suggested_item_details['description']})"
         else:
              # Fallback if no specific recommendation found (e.g., they have everything!)
              response_text = "Hmm, based on what you have, everything looks perfect! Or maybe you'd like to browse the 'menu' for something completely different?"

         response_text += "\n" + random_choice(PERSONALITY["ask_something_else"])
         order_state["status"] = "ordering" # User is getting recommendations, still in ordering flow
         if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"] # Clear clarification state


    elif intent == "start_checkout":
        items_count = sum(order_state["items"].values()) # Count total quantity
        if items_count == 0:
            response_text = random_choice(PERSONALITY["empty_order"]) + " Add some food before checking out!"
            order_state["status"] = "browsing" # Cannot checkout empty order
        else:
            response_text = format_order_summary(order_state)
            response_text += "\nReady to confirm and place your order? Type 'confirm' or 'yes'. Type anything else to add more items."
            order_state["status"] = "checkout" # Transition to checkout state, waiting for confirmation
        if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"] # Clear clarification state


    elif intent == "confirm_checkout":
         # This intent is only processed if status was "checkout" (handled in parse_user_input_nlp)
         # In a real app, this would trigger payment processing and sending the order to the kitchen system (POS).
         response_text = "Awesome! Your simulated order is placed! Processing payment now... (This is where real payment/POS integration happens) ✅"
         response_text += "\n" + random_choice(PERSONALITY["goodbye"])
         order_state["status"] = "completed" # Final state for this interaction
         # Clear the order after successful (simulated) checkout
         order_state["items"] = {}
         order_state["last_item_added"] = None
         if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"]


    elif intent == "cancel_checkout":
         # This intent is only processed if status was "checkout"
         response_text = "Okay, staying on the order page. What else would you like to add?"
         response_text += "\n" + random_choice(PERSONALITY["ask_something_else"])
         order_state["status"] = "ordering" # Go back to ordering flow
         if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"]


    elif intent == "goodbye":
        response_text = random_choice(PERSONALITY["goodbye"])
        order_state["status"] = "completed" # End the conversation state
        # Clear the order if user leaves explicitly
        order_state["items"] = {}
        order_state["last_item_added"] = None
        if "clarifying_item_id" in order_state: del order_state["clarifying_item_id"]


    # --- Handle Unknown Intent ---
    # If response_text is still None, it means the intent was "unknown" or didn't trigger a specific response logic block
    if response_text is None:
        response_text = random_choice(PERSONALITY["clarify"])
        if order_state["status"] in ["browsing", "ordering"]:
            response_text += "\nYou can try asking to 'show menu', 'add [item name]', 'show my order', or 'checkout'."
        elif order_state["status"] == "checkout":
             response_text += "\nType 'confirm' to place your order or anything else to go back."
        elif order_state["status"] == "waiting_for_clarification":
             item_id_being_clarified = order_state.get("clarifying_item_id")
             if item_id_being_clarified and item_id_being_clarified in PERSONALITY["clarify_item_needed"]:
                 # Re-prompt the specific clarification question
                 response_text = random_choice(PERSONALITY["clarify_item_needed"][item_id_being_clarified])
             else:
                 # Fallback clarification prompt
                 response_text += "\nI'm waiting for you to clarify that item. Please be specific!"

        # State remains the same for unknown inputs


    print(f"Debug: Order State after processing: {order_state}")
    return response_text

# --- Flask App Setup ---
app = Flask(__name__)
# In a real app, you'd use a secure secret key and more robust session management
# app.secret_key = 'your_super_secret_key'

# --- Simple in-memory storage for session states (Not production-ready!) ---
# In production, use Flask-Session, database, or other persistent storage
user_sessions = {}


@app.route('/')
def index():
    """Serves the main chat HTML page."""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handles incoming chat messages from the frontend."""
    data = request.get_json()
    user_message = data.get('message', '')
    # Get the user_id sent from the frontend's localStorage
    incoming_user_id = data.get('user_id')

    # --- Get or create user session state ---
    current_user_id = incoming_user_id # Start by assuming the incoming ID is the one to use

    # If no ID came from frontend OR the ID is not known to the server (server restarted, etc.), create a new session
    if current_user_id is None or current_user_id not in user_sessions:
        new_user_id = str(uuid.uuid4()) # Generate a new ID
        user_sessions[new_user_id] = {
            "items": {}, # Start with an empty order
            "status": "browsing", # Start in browsing state
            "last_item_added": None,
            "history": [] # Optional: store conversation history
            # Add any other initial state variables here
        }
        print(f"Debug: Created new session for user_id: {new_user_id} (Incoming ID was: {incoming_user_id})")
        current_user_id = new_user_id # Use the newly generated ID for this request

    # At this point, current_user_id holds the valid session ID (either incoming or newly generated)
    # Load the order state for this user ID
    order_state = user_sessions[current_user_id]

    print(f"Debug: Received message '{user_message}' for user_id: {current_user_id} in state: '{order_state['status']}'") # Debugging start of request

    # --- Process the message ---
    # 1. NLP/NLU: Parse the user's input
    # FIX: Pass order_state to parse_user_input_nlp
    parsed_input = parse_user_input_nlp(user_message, order_state)

    # 2. Dialog Management & Response Generation: Update state and get response
    # Pass the mutable order_state dictionary so generate_bot_response can update it
    bot_response_text = generate_bot_response(parsed_input, order_state)

    # 3. State is updated within generate_bot_response (mutable dict)
    # user_sessions[current_user_id] is already the updated order_state

    # --- Return response to frontend ---
    response_data = {
        "response": bot_response_text,
        "user_id": current_user_id, # Send back the ID that was actually used (ensures frontend stays in sync)
        "status": order_state["status"] # Send current status back so frontend can react (e.g., disable input)
    }
    # print(f"Debug: Sending response: {response_data}") # Debugging response sent
    return jsonify(response_data)

if __name__ == '__main__':
    # Run the Flask app
    # In production, use a more robust WSGI server like Gunicorn or uWSGI
    # host='0.0.0.0' makes it accessible from other machines on the network (use with caution)
    app.run(debug=True, port=5000, host='127.0.0.1') # debug=True allows auto-reloading and shows errors