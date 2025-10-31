ZIPNAME = addon.zip

clean:
	rm -rf *.pyc __pycache__/ .DS_Store $(ZIPNAME)

pack:
	make clean
	zip -r $(ZIPNAME) *
