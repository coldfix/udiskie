po: $(wildcard *.po)
mo: $(addsuffix .mo, $(basename $(wildcard *.po)))
all: po mo

%.mo: %.po
	msgfmt $< -o $@

%.po: udiskie.pot
	@if [ -f $@ ]; then \
		$(echo) msgmerge -q -U $@ $<;\
	else \
		$(echo) msginit -o=$@ -i=$<;\
	fi

# Make .pot phony because make doesn't play well with git
.PHONY: udiskie.pot
udiskie.pot:
	find ../udiskie -name '*.py' | xgettext -o $@ -f - \
		-LPython --from-code=UTF-8 \
		--package-name=udiskie \
		--package-version=$(version) \
		--copyright-holder="Thomas Gläßle"
	sed -i $@ -e "s/YEAR/$$(date +%Y)/"
	@if [ $$( git diff --numstat -- $@ | cut -f1 ) -le 1 ]; then \
		$(echo) git checkout -- $@; \
	fi

version = $(shell sed -ne "s/__version__ = //p" ../udiskie/__init__.py)
echo = _() { echo "$$@"; "$$@"; }; _
