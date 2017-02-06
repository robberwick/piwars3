from numpy import interp

class Servo_Controller():

    def __init__(self,
                 min,
                 mid,
                 max,
                 bReverse):
                 
        self.servo_min = min;
        self.servo_mid = mid;
        self.servo_max = max;
        self.servo_reversed = bReverse;
        
    def micros(self, fSpeed):
        # Map an abstract speed in [1, -1] to servo control microseconds
        micros = 0
        if( self.servo_reversed ):
            micros = interp(fSpeed, [-1, 1],[self.servo_max, self.servo_min])
        else:
            micros = interp(fSpeed, [-1, 1],[self.servo_min, self.servo_max])
            
        return int(micros)
        
    def set_min(newmin):
        self.servo_min = newmin
        
    def set_max(newmax):
        self.servo_max = newmax
        
    def set_mid(newmid):
        self.servo_mid = newmid
        
    def set_reverse(new_rev):
        self.servo_reversed = new_rev