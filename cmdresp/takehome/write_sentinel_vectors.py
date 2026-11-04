from scenarios import cases

errors = [case for case in cases() if case[3][0]]
with open('sentinel_vectors.txt', 'w', encoding='ascii') as out:
    print(len(errors), file=out)
    for name, words, _, status in errors:
        print(name, len(words), status[1], status[2], file=out)
        for word, last in words:
            print(f'{word:08x} {int(last)}', file=out)
