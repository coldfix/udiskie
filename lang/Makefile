all: po mo

po: $(wildcard *.po)
mo: $(addsuffix .mo, $(basename $(wildcard *.po)))

%.mo: %.po
	msgfmt $< -o $@

%.po: udiskie.pot
	if [ -f $@ ]; then \
        msgmerge --update $@ $< ;\
    else \
        msginit --output=$@ --input=$< --locale=en_US ;\
    fi

# Make .pot phony because make doesn't play well with git
.PHONY: udiskie.pot
udiskie.pot: $(wildcard ../udiskie/*.py)
	xgettext --language=Python --keyword=_ --output=$@ --from-code=UTF-8 $^
	if [[ $$( git diff --numstat -- $@ | cut -f1 ) -le 1 ]]; then \
		git checkout -- $@; \
	fi
