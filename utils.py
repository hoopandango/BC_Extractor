from Crypto.Util.Padding import unpad

def unpad_file(file_name):
	# TODO: unpad files during extraction, and for the love of god unpad them properly.
	# Checks if file is present and unpads it (if needed)
	try:
		with open(file_name, encoding = 'utf-8') as fl:
			fltext = fl.read()
	except:
		return False  # File not found
	
	try:
		fltext = unpad(fltext.encode(),block_size = 16).decode()
	except:
		pass

	lines = fltext.split('\n')
	if lines[0].count(',') - lines[-1].count(',') > 2 or lines[0].count('|') - lines[-1].count('|') > 2 or len(lines[-1].split(',')) + len(lines[-1].split('|')) + len(lines[-1].split('\t')) < 4:
		lines = lines[:-1]  # Drops Padding Rows

	fltext = '\n'.join(lines)
	
	with open(file_name,'w', encoding = 'utf-8') as fl:
		fl.write(fltext)
	return True  # File unpadded