import src_extractors.items_extractor
import src_extractors.gatya_extractor
import src_extractors.mission_extractor
import src_extractors.units_extractor
import src_extractors.talent_extractor
import src_extractors.combo_extractor

def run_all():
	units_extractor.extract()
	items_extractor.updateItems()
	gatya_extractor.extract()
	mission_extractor.updateItems()
	combo_extractor.run()
	talent_extractor.updateTalentsTable()
	talent_extractor.updateLevelsTable()
	talent_extractor.updateDescriptionsTable()
	
	input("Please update combos table from out_intermediates")
	combo_extractor.run()
	