from src import event_data_printers
def run(ver: str):
	query = {
		"version": ver,
		"diffs": {
			"Gatya": "",
			"Item": "",
			"Sale": ""
		},
		"fetch": True
	}
	return event_data_printers.process(query)[1]

print("\n".join([x for x in run("en")]))
