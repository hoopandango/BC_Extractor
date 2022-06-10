import src_extractors.items_extractor
import src_extractors.gatya_extractor
import src_extractors.mission_extractor
import src_extractors.units_extractor
import src_extractors.talent_extractor
import src_extractors.combo_extractor
import src_extractors.enemy_extractor
from src_backend.local_readers import Readers

def run_all():
	units_extractor.extract()
	enemy_extractor.extract()
	items_extractor.extract()
	Readers.reload()
	gatya_extractor.extract()
	mission_extractor.extract()
	talent_extractor.extract()
	combo_extractor.extract()
	