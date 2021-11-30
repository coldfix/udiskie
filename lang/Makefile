version = $(shell sed -ne "s/__version__ = //p" ../udiskie/__init__.py)
sources = find ../udiskie -name '*.py'
echo = _() { echo "$$@"; "$$@"; }; _

po: $(wildcard *.po)
mo: $(addsuffix .mo, $(basename $(wildcard *.po)))
all: po mo

%.mo: %.po
	msgfmt $< -o $@

%.po: udiskie.pot
	@if [ -f $@ ]; then \
		$(echo) msgmerge -q -U $@ $< && touch $@;\
	else \
		$(echo) msginit -o $@ -i $< -l $*;\
	fi

udiskie.pot: $(shell $(sources))
	$(sources) | xgettext -o $@ -f - \
		-LPython --from-code=UTF-8 \
		--package-name=udiskie \
		--package-version=$(version) \
		--copyright-holder="Thomas Gläßle"
	sed -i $@ -e "s/YEAR/$$(date +%Y)/"
	@if [ $$( git diff --numstat -- $@ | cut -f1 ) -le 1 ]; then \
		$(echo) git checkout -- $@; \
	fi
