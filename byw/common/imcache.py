
class imcache:
    def __init__(self,size):
        # TODO: map for larger caches
        self.size = size
        self.cache = {}
    def get(self,f,*args,**kwargs):
        return f(*args,**kwargs) # Hitting memory issues. Disabling cache to test
        if not f in self.cache:
            self.cache[f] = [0,[],[]]
        c = self.cache[f]
        if len(self.cache) > 32:
            print "Cachelen:",len(self.cache)
        if not [args,kwargs] in c[1]:
            res = f(*args,**kwargs)
            if c[0] < self.size:
                c[1].append([args,kwargs])
                c[2].append(res)
                c[0] += 1
            else:
                idx = c[0]%self.size
                c[1][idx] = [args,kwargs]
                c[2][idx] = res
            return res
        else:
            idx = c[1].index([args,kwargs])
            return c[2][idx]
    def __call__(self,*args,**kwargs):
        return self.get(*args,**kwargs)


def main():
    print "Test imcache...",
    c = imcache(32)

    def f1(a,b=0):
        return a+b
    def f2(a,b):
        return a+b

    for i in xrange(4):
        for j in xrange(16):
            f1r = c(f1,i,j)
            f2r = c(f2,i,j)
            assert(f1r == f2r == i+j)
    print "pass"
    
if __name__ == "__main__": main()
        
