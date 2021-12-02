#! /usr/bin/env python

def read_tsv(fname):
    with open(fname) as f:
        return [line.strip('\n').split('\t') for line in f]


def make_table_dict(columns, *rows):
    return {
        row[0]: dict(zip(columns[1:], row[1:]))
        for row in rows
    }


def dicts_items(a, b):
    for k, va in a.items():
        yield (k, va, b.get(k))


def summarize_entry(a, b, key):
    va = int(a[key])
    vb = int(b[key])
    if vb > va:
        return f'{va} ↗️ {vb}'
    elif vb == va:
        return f'{vb}'
    else:
        return f'{va} ↘️ {vb}'


def tabularize(*rows, align):
    rows = [[' {} '.format(x) for x in row] for row in rows]
    cols = list(zip(*rows))
    widths = [
        max(3, max(len(x) for x in col))
        for col in cols
    ]
    lines = [
        ['{:{}{}}'.format(val, align_, width)
         for val, align_, width in zip(row, align, widths)]
        for row in rows
    ]
    INFO = {'<': ':{}-', '^': ':{}:', '>': '-{}:'}
    lines.insert(1, [
        INFO[align_].format('-' * (width - 2))
        for align_, width in zip(align, widths)
    ])
    return ''.join([
        '|{}|\n'.format('|'.join(line))
        for line in lines
    ])


def main(url='https://github.com/coldfix/udiskie/blob/master/lang/'):
    href = '[{0}]({1}{0})' if url else '{0}'
    before = make_table_dict(*read_tsv('before.tsv'))
    after = make_table_dict(*read_tsv('after.tsv'))
    columns = [
        'File',
        'Untranslated',
        'Translated',
        'Out-of-date',
        'Obsolete',
        '% Complete',
    ]
    summary = [
        [
            href.format(filename, url),
            summarize_entry(ra, rb, 'Untranslated'),
            summarize_entry(ra, rb, 'Translated'),
            summarize_entry(ra, rb, 'Fuzzy'),
            summarize_entry(ra, rb, 'Obsolete'),
            summarize_entry(ra, rb, '%'),
        ]
        for filename, rb, ra in dicts_items(before, after)
    ]
    print(tabularize(columns, *summary, align='<>>>>>'))


if __name__ == '__main__':
    main()
