#! /usr/bin/env bash

count_strings() {
    grep '^msgid "' | tail -n +2 | wc -l
}

folder=$(dirname "$(readlink -f "$BASH_SOURCE")")
n_total=$(msgattrib "$folder/udiskie.pot" | count_strings)

echo -e "File\tUntranslated\tTranslated\tFuzzy\tObsolete\t%"
for po in "$folder"/*.po; do
    n_u=$(msgattrib $po --untranslated | count_strings)
    n_t=$(msgattrib $po --translated   | count_strings)
    n_f=$(msgattrib $po --fuzzy        | count_strings)
    n_o=$(msgattrib $po --obsolete     | count_strings)
    percent=$( echo "scale=0; ($n_total-$n_u)*100/$n_total" | bc )

    echo -e "$(basename "$po")\t$n_u\t$n_t\t$n_f\t$n_o\t$percent"
done
