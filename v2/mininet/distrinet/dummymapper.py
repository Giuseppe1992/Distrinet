class DummyMapper(object):
    def __init__(self, places={}):
        self.places = places

    def place(self, node):
        return self.places[node]

    def placeLink(self, link):
        return ({}, {})

class RoundRobbinMapper(DummyMapper):
    def __init__(self, physical=[]):
        self.physical = physical
        self.i = 0

    def place(self, node):
        self.i = (self.i + 1 ) % len(self.physical)
        return self.physical[self.i]

if __name__ == "__main__":
    mapper = DummyMapper(places={"h1": "master1",
                                 "h2": "master1",
                                 "s1": "slave1"
                                })

    print (mapper.place("h1"))
    print (mapper.place("h2"))
    print (mapper.place("s1"))

    print ("")
    mapper = RoundRobbinMapper(physical=["master1", "slave1"])
    for i in range(1,10):
        print (mapper.place(i))
        print (mapper.placeLink(i))
