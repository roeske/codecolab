import re

_card_link_matcher = re.compile("#\d+")

def make_card_links(text, project_name):
    matches = _card_link_matcher.findall(text)
    for m in matches:
        try:
            card_id = int(m[1:])
        except:
            continue

        url = "/p/%s/boards?card=%d" % (project_name, card_id)
        text = text.replace(m, '<a href="%s">%s</a>' % (url, m))
    return text
