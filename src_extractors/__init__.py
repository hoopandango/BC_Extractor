import src_extractors.items_extractor
import src_extractors.gatya_extractor
import src_extractors.mission_extractor
import src_extractors.units_extractor

def run_all():
	units_extractor.extract()
	items_extractor.updateItems()
	gatya_extractor.extract()
	mission_extractor.updateItems()
	