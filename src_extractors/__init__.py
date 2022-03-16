import src_extractors.items_extractor
import src_extractors.gatya_extractor
import src_extractors.mission_extractor
import src_extractors.units_extractor
import src_extractors.talent_extractor
import src_extractors.combo_extractor

def run_all():
	units_extractor.extract()
	items_extractor.extract()
	gatya_extractor.extract()
	mission_extractor.extract()
	talent_extractor.extract()
	combo_extractor.extract()
	input()
	combo_extractor.extract()
	