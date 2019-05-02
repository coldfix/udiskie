
all: en_US.po es_ES.po sk_SK.po

%.po: udiskie.pot
	if [ -f $@ ]; then \
        msgmerge --update $@ $< ;\
    else \
        msginit --output=$@ --input=$< --locale=en_US ;\
    fi

udiskie.pot: $(wildcard ../udiskie/*.py)
	xgettext --language=Python --keyword=_ --output=$@ --from-code=UTF-8 $^


