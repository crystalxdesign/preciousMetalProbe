"""Generate an exact vector wiring diagram; no generated-image interpretation."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, Arc

OUT = Path(__file__).resolve().parent
fig, ax = plt.subplots(figsize=(17, 11))
fig.patch.set_facecolor('#f7fafc')
ax.set_facecolor('#f7fafc')
ax.set_xlim(0, 17); ax.set_ylim(0, 11); ax.axis('off')
ink='#163348'; wire='#20536b'; blue='#0b779e'; orange='#ae6416'

def text(x,y,s,size=11,**kw):
    ax.text(x,y,s,fontsize=size,color=ink,ha=kw.pop('ha','center'),va='center',**kw)
def line(points,color=wire,lw=1.7,**kw):
    ax.plot(*zip(*points),color=color,lw=lw,**kw)
def dot(x,y): ax.add_patch(Circle((x,y),.045,color=wire))
def ground(x,y):
    line([(x,y),(x,y-.15)])
    for dy,w in [(0,.22),(.09,.15),(.18,.07)]: line([(x-w,y-.15-dy),(x+w,y-.15-dy)])
def resistor(x1,y1,x2,y2,label,above=True):
    if y1==y2:
        mid=(x1+x2)/2
        line([(x1,y1),(mid-.30,y1)])
        ax.add_patch(Rectangle((mid-.30,y1-.10),.60,.20,fill=False,ec=wire,lw=1.7))
        line([(mid+.30,y1),(x2,y2)])
        text(mid,y1+(.35 if above else -.35),label,11)
    else:
        mid=(y1+y2)/2
        line([(x1,y1),(x1,mid+.28)])
        ax.add_patch(Rectangle((x1-.10,mid-.28),.20,.56,fill=False,ec=wire,lw=1.7))
        line([(x1,mid-.28),(x2,y2)])
        text(x1-.28,mid,label,10,ha='right')
def capacitor(x,y1,y2,label,side='right'):
    mid=(y1+y2)/2
    line([(x,y1),(x,mid+.07)])
    line([(x-.23,mid+.07),(x+.23,mid+.07)])
    line([(x-.23,mid-.07),(x+.23,mid-.07)])
    line([(x,mid-.07),(x,y2)])
    text(x+(.32 if side=='right' else -.32),mid,label,10,
         ha='left' if side=='right' else 'right')
def amp(x,y,label,plus_pin,minus_pin,out_pin):
    ax.add_patch(Polygon([(x,y-.7),(x,y+.7),(x+1.35,y)],closed=True,
                         fc='#e6f3f8',ec=blue,lw=1.8))
    text(x+.14,y+.35,'+',12); text(x+.14,y-.35,'−',12)
    text(x+.52,y,label,11)
    text(x-.08,y+.52,str(plus_pin),9,ha='right')
    text(x-.08,y-.52,str(minus_pin),9,ha='right')
    text(x+1.46,y+.18,str(out_pin),9)

text(.5,10.45,'LC metal-sample capture • Raspberry Pi Pico / RP2040',23,ha='left',weight='bold')
text(.5,9.95,'470 µH air-core coil + 47 nF tank  |  5 µs excitation  |  500 kS/s ADC + DMA  |  USB training data',12,ha='left')

# Excitation switch and resistor.
text(.7,8.25,'+3V3',12,weight='bold')
line([(.7,8),(1.55,8)])
ax.add_patch(Rectangle((1.55,7.45),1.8,1.1,fc='#fff4e3',ec=orange,lw=1.8))
text(2.45,8.34,'U2 TMUX1101',11,weight='bold')
text(2.45,8.77,'DBV / SOT-23-5',9)
line([(1.55,8),(1.9,8)]); line([(2.0,8),(2.75,8.15)],color=orange)
line([(2.86,8),(3.35,8)])
text(1.64,7.76,'S 2',9,ha='left'); text(3.24,7.76,'D 1',9,ha='right')
text(2.45,7.58,'SEL 4',9)
line([(2.45,7.45),(2.45,6.3)])
text(2.0,5.95,'GP15 / pin 20',11,weight='bold')
line([(2.45,6.65),(3.55,6.65)])
resistor(3.55,6.65,3.55,5.55,'R5\n100 kΩ')
ground(3.55,5.55)
resistor(3.35,8,5.0,8,'R3 330 Ω')
line([(5,8),(8.5,8),(8.5,7.95),(9,7.95)])
dot(6,8); dot(8,8)
text(6.8,8.4,'TANK',12,weight='bold')

# Parallel LC tank between TANK and BIAS.
capacitor(6,8,5.2,'C3 47 nF\nC0G / film',side='left')
line([(8,8),(8,7.325)])
for center in np.linspace(7.20,6.20,5):
    ax.add_patch(Arc((8,center),.46,.25,theta1=-90,theta2=90,ec=wire,lw=1.7))
line([(8,6.075),(8,5.2)])
text(7.7,6.7,'L1\n470 µH\nair-core coil',11,ha='right')
text(7,5.52,'Parallel LC',10)
line([(5.8,5.2),(8,5.2)]); dot(6,5.2); dot(8,5.2)

# Measurement buffer and ADC network.
amp(9,7.6,'U1B',5,6,7)
line([(10.35,7.6),(10.65,7.6)])
line([(10.65,7.6),(10.65,6.53),(8.8,6.53),(8.8,7.25),(9,7.25)])
dot(10.65,7.6)
resistor(10.65,7.6,12.5,7.6,'R4 100 Ω')
line([(12.5,7.6),(13.7,7.6)]); dot(12.9,7.6)
capacitor(12.9,7.6,6.2,'C4\n4.7 nF',side='left'); ground(12.9,6.2)

# Pico block and named supply/control nets.
ax.add_patch(Rectangle((13.7,5.0),2.8,4.1,fc='#e5f3e9',ec='#328455',lw=1.8))
text(15.1,8.72,'Raspberry Pi Pico',13,weight='bold')
text(15.1,8.35,'RP2040',12)
text(13.9,7.75,'GP26 / ADC0',11,ha='left'); text(13.9,7.43,'physical pin 31',9,ha='left')
text(15.1,6.82,'USB → PC logger',12,weight='bold')
text(15.1,6.4,'2048 samples / capture',10)
text(15.1,5.85,'GP15: pin 20 → SEL',10)
text(15.1,5.48,'3V3: pin 36  •  AGND: pin 33',10)

# Buffered midrail divider.
text(.6,4.65,'1.65 V bias generator',13,ha='left',weight='bold')
text(1.0,4.26,'+3V3',11)
resistor(1,4.05,1,2.8,'R1 10 kΩ')
dot(1,2.8); text(1,2.57,'MID',9)
resistor(1,2.8,1,1.3,'R2 10 kΩ')
ground(1,1.3)
line([(1,2.8),(3.7,2.8),(3.7,3.35),(4.3,3.35)])
dot(2.0,2.8); dot(2.95,2.8)
capacitor(2,2.8,1.3,'C1\n10 µF',side='left'); ground(2,1.3)
capacitor(2.95,2.8,1.3,'C2\n100 nF'); ground(2.95,1.3)
amp(4.3,3.0,'U1A',3,2,1)
line([(5.65,3),(5.8,3),(5.8,5.2)])
dot(5.8,3)
line([(5.8,3),(5.8,2.2),(4.05,2.2),(4.05,2.65),(4.3,2.65)])
text(5.9,4.3,'BIAS\n≈1.65 V',11,ha='left',weight='bold')

# Supply wiring is shown as a table to keep all pins explicit without crossings.
ax.add_patch(Rectangle((8.9,.9),7.6,3.4,fc='white',ec='#b3c9d3',lw=1.2))
text(9.15,4.0,'Power and construction notes',13,ha='left',weight='bold')
notes=[
 'U1 = OPA2320AID (SOIC-8): pin 8 → +3V3; pin 4 → AGND.',
 'U2 = TMUX1101DBVR: pin 5 → +3V3; pin 3 → AGND.',
 'C5: 100 nF at U1 pins 8–4; C6: 100 nF at U2 pins 5–3.',
 'C7: 10 µF across +3V3 / AGND near the analogue section.',
 'All ground symbols → Pico AGND (pin 33).',
 'Use Pico 3V3(OUT), pin 36. Leave ADC_VREF unchanged.',
 'Keep tank leads short; coil away from USB cable and metal fixings.',
 'Check TANK and ADC voltage with a scope before connecting GP26.',
]
for i,s in enumerate(notes): text(9.15,3.6-i*.31,s,10,ha='left')
text(.55,.53,'Voltage across LC = TANK − BIAS.  Subtract pre-pulse baseline from ADC samples.  Target waveform: comfortably within 0.3–3.0 V.',11,ha='left')
text(.55,.16,'Connectivity schematic, not a PCB layout. Component values are prototype starting values; verify the actual coil response.',9,ha='left')
fig.subplots_adjust(left=.015,right=.99,top=.99,bottom=.015)
fig.savefig(OUT/'preciousMetalProbe.svg',facecolor=fig.get_facecolor())
fig.savefig(OUT/'preciousMetalProbe.png',dpi=160,facecolor=fig.get_facecolor())
print(OUT/'preciousMetalProbe.png')
