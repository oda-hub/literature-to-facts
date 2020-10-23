oda-kb  reason '?ig paper:original_event ?lve . ?lvg paper:lvc_event ?lve; paper:lvc_event_utc ?lvu .'  '?ig paper:original_event_utc ?lvu' -c


FROM_GCN=26908 TO_GCN=26909 python facts/learn.py -m gcnsall -m adsabs    learn -g
