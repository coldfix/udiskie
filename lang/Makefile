version = $(shell sed -ne "s/__version__ = //p" ../udiskie/__init__.py)
sources = find ../udiskie -name '*.py'
echo = _() { echo "$$@"; "$$@"; }; _

po: $(wildcard *.po)
mo: $(addsuffix .mo, $(basename $(wildcard *.po)))
	@if [ -z "$$TEXTDOMAINDIR" ]; then\
		echo In order to activate the newly built localization files, type:;\
		echo;\
		echo     export TEXTDOMAINDIR=\"$$(readlink -f ../build/locale)\"; \
	fi

all: po mo

clean:
	rm -rf *.po~ *.mo locale

%.mo: %.po
	msgfmt $< -o $@
	@mkdir -p ../build/locale/$*/LC_MESSAGES/
	@cp $@ ../build/locale/$*/LC_MESSAGES/udiskie.mo

en_US.po: udiskie.pot
	msginit -o $@ -i $< -l en_US --no-translator

%.po: udiskie.pot
	@if [ -f $@ ]; then \
		$(echo) msgmerge -q -U $@ $< && touch $@;\
	else \
		$(echo) msginit -o $@ -i $< -l $*;\
	fi

udiskie.pot: $(shell $(sources))
	$(sources) | sort | xgettext -o $@ -f - \
		-LPython --from-code=UTF-8 \
		--package-name=udiskie \
		--package-version=$(version) \
		--copyright-holder="Thomas Gläßle"
	sed -i $@ -e "s/YEAR/$$(date +%Y)/"
	@if [ $$( git diff --numstat -- $@ | cut -f1 ) -le 1 ]; then \
		$(echo) git checkout -- $@; \
	fi
