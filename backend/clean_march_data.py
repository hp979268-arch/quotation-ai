import search_engine

search_engine.load_index()

initial_count = len(search_engine.stored_items)
print(f"Initial total items: {initial_count}")

# Filter out March'26 items
new_items = [
    item for item in search_engine.stored_items 
    if item.get("source") != "Kohler_Pricebook (March'26)"
]

search_engine.stored_items.clear()
search_engine.stored_items.extend(new_items)

final_count = len(search_engine.stored_items)
removed_count = initial_count - final_count

print(f"Removed items: {removed_count}")
print(f"Final total items: {final_count}")

if removed_count > 0:
    search_engine.save_index()
    print("Database updated and index rebuilt successfully.")
else:
    print("No items needed to be removed.")
