import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMascotStore } from '../../store/mascotStore'
import type { MascotStatus } from '../../store/mascotStore'

const STATUS_TEXT: Record<MascotStatus, string> = {
  idle:     '哼，还不开始扫描？',
  scanning: '让我仔细看看你的代码...',
  found:    '你看看你写的什么东西！',
}

const STATUS_CLASS: Record<MascotStatus, string> = {
  idle:     'bg-[#2a2a4a] text-[#8899cc] border-[#4455aa]',
  scanning: 'bg-[#1a3a1a] text-[#44cc44] border-[#228822]',
  found:    'bg-[#3a1a1a] text-[#ff4444] border-[#aa2222]',
}

const ANIM_CLASS: Record<MascotStatus, string> = {
  idle:     'anim-idle',
  scanning: 'anim-scan',
  found:    'anim-found',
}

// 每种状态下的嘴、眉毛位置 [x, y, w, h]
const MOUTH: Record<string, [number, number, number, number]> = {
  idle:     [28, 35, 8, 1],
  scanning: [28, 35, 8, 1],
  found:    [25, 33, 14, 2],
}
const BROW_L: Record<string, [number, number, number, number]> = {
  idle:     [17, 13, 7, 2],
  scanning: [16, 12, 7, 2],
  found:    [15, 14, 7, 2],
}
const BROW_R: Record<string, [number, number, number, number]> = {
  idle:     [40, 13, 7, 2],
  scanning: [41, 12, 7, 2],
  found:    [42, 14, 7, 2],
}

const EYE_L = { x: 22, y: 18 }
const EYE_R = { x: 43, y: 18 }
const MAX_R = 2

function setRect(r: SVGRectElement | null, [x, y, w, h]: number[]) {
  if (!r) return
  r.setAttribute('x', String(x))
  r.setAttribute('y', String(y))
  r.setAttribute('width', String(w))
  r.setAttribute('height', String(h))
}

export function MascotCard() {
  const status = useMascotStore((s) => s.status)
  const nav = useNavigate()
  const svgRef = useRef<SVGSVGElement>(null)
  const plRef = useRef<SVGGElement>(null)
  const prRef = useRef<SVGGElement>(null)
  const mouthRef = useRef<SVGRectElement>(null)
  const browLRef = useRef<SVGRectElement>(null)
  const browRRef = useRef<SVGRectElement>(null)
  const sockLRef = useRef<SVGRectElement>(null)
  const sockRRef = useRef<SVGRectElement>(null)
  const reportRef = useRef<SVGGElement>(null)
  const sweatRef = useRef<SVGGElement>(null)
  const glowRef = useRef<SVGRectElement>(null)
  const targetL = useRef(EYE_L)
  const targetR = useRef(EYE_R)
  const curL = useRef(EYE_L)
  const curR = useRef(EYE_R)

  // 更新面部表情
  useEffect(() => {
    setRect(mouthRef.current, MOUTH[status] ?? MOUTH.idle)
    setRect(browLRef.current, BROW_L[status] ?? BROW_L.idle)
    setRect(browRRef.current, BROW_R[status] ?? BROW_R.idle)
    const pColor = status === 'found' ? '#cc2222' : '#1a1a1a'
    plRef.current?.querySelectorAll('rect').forEach((r) => r.setAttribute('fill', pColor))
    prRef.current?.querySelectorAll('rect').forEach((r) => r.setAttribute('fill', pColor))
    // 道具
    if (reportRef.current) reportRef.current.style.display = status === 'found' ? '' : 'none'
    if (sweatRef.current) sweatRef.current.style.display = 'none'
  }, [status])

  // 光晕动画
  useEffect(() => {
    let raf = 0
    let phase = 0
    const glow = glowRef.current
    if (!glow) return
    const colors: Record<string, string> = { idle: 'transparent', scanning: '#44cc44', found: '#ff4444' }
    const color = colors[status] ?? 'transparent'
    if (color === 'transparent') {
      glow.setAttribute('opacity', '0')
      return
    }
    glow.setAttribute('stroke', color)
    const tick = () => {
      phase += 0.06
      glow.setAttribute('opacity', (0.3 + 0.3 * Math.sin(phase)).toFixed(3))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [status])

  // 眨眼
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    const blink = () => {
      const sL = sockLRef.current, sR = sockRRef.current
      setRect(sL, [18, 17, 7, 1])
      setRect(sR, [39, 17, 7, 1])
      setTimeout(() => {
        setRect(sL, [18, 15, 7, 6])
        setRect(sR, [39, 15, 7, 6])
      }, 120)
      timer = setTimeout(blink, 2000 + Math.random() * 3000)
    }
    timer = setTimeout(blink, 1500)
    return () => clearTimeout(timer)
  }, [])

  // 眼球追踪（带阻尼）
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const onMouse = (e: MouseEvent) => {
      const pt = svg.createSVGPoint()
      pt.x = e.clientX; pt.y = e.clientY
      const p = pt.matrixTransform(svg.getScreenCTM()!.inverse())
      const f = (mx: number, my: number, eye: { x: number; y: number }) => {
        const dx = mx - eye.x, dy = my - eye.y
        const a = Math.atan2(dy, dx)
        const d = Math.min(Math.hypot(dx, dy), MAX_R)
        return { x: eye.x + Math.cos(a) * d, y: eye.y + Math.sin(a) * d }
      }
      targetL.current = f(p.x, p.y, EYE_L)
      targetR.current = f(p.x, p.y, EYE_R)
    }
    window.addEventListener('mousemove', onMouse)

    let raf = 0
    const smooth = () => {
      const S = 0.12
      curL.current = { x: curL.current.x + (targetL.current.x - curL.current.x) * S, y: curL.current.y + (targetL.current.y - curL.current.y) * S }
      curR.current = { x: curR.current.x + (targetR.current.x - curR.current.x) * S, y: curR.current.y + (targetR.current.y - curR.current.y) * S }
      plRef.current?.setAttribute('transform', `translate(${curL.current.x.toFixed(2)},${curL.current.y.toFixed(2)})`)
      prRef.current?.setAttribute('transform', `translate(${curR.current.x.toFixed(2)},${curR.current.y.toFixed(2)})`)
      raf = requestAnimationFrame(smooth)
    }
    raf = requestAnimationFrame(smooth)

    return () => {
      window.removeEventListener('mousemove', onMouse)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <div
      className="flex flex-col items-center gap-3 select-none cursor-pointer hover:opacity-80 transition-opacity"
      onClick={() => nav('/chat')}
      title="点击和码医生对话"
    >
      <p className="text-xs font-black uppercase tracking-[0.3em] text-black">马 医 生</p>

      <svg
        ref={svgRef}
        width="192" height="216"
        viewBox="0 0 64 72"
        shapeRendering="crispEdges"
        style={{ imageRendering: 'pixelated' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <style>{`
          .anim-idle .body-g { animation: a-idle 3s ease-in-out infinite; }
          .anim-idle .arm-l { animation: a-cross 3s ease-in-out infinite; transform-origin: 19px 44px; }
          .anim-idle .arm-r { animation: a-cross 3s ease-in-out .5s infinite; transform-origin: 47px 44px; }
          .anim-idle .leg-l { animation: a-tap .5s ease-in-out infinite; transform-origin: 30px 67px; }
          .anim-idle .head-g { animation: a-tilt 3s ease-in-out infinite; transform-origin: 32px 13px; }
          .anim-scan .body-g { animation: a-lean 2s ease-in-out infinite; }
          .anim-scan .arm-r { animation: a-steth 2s ease-in-out infinite; transform-origin: 47px 44px; }
          .anim-scan .head-g { animation: a-nod 2s ease-in-out infinite; transform-origin: 32px 13px; }
          .anim-found .body-g { animation: a-shake .2s linear infinite; }
          .anim-found .arm-l { animation: a-wave .35s ease-in-out infinite; transform-origin: 19px 44px; }
          .anim-found .arm-r { animation: a-wave .35s ease-in-out .18s infinite; transform-origin: 47px 44px; }
          @keyframes a-idle { 0%,100%{transform:translate(0)} 45%{transform:translate(2px,0)} 80%{transform:translate(-1px,0)} }
          @keyframes a-cross { 0%,100%{transform:rotate(0)} 40%{transform:rotate(-10deg)} 70%{transform:rotate(3deg)} }
          @keyframes a-tap { 0%,100%{transform:rotate(0)} 50%{transform:rotate(7deg)} }
          @keyframes a-tilt { 0%,100%{transform:rotate(0)} 35%{transform:rotate(3deg)} 65%{transform:rotate(-2deg)} }
          @keyframes a-lean { 0%,100%{transform:translate(0)} 50%{transform:translate(-4px,0)} }
          @keyframes a-steth { 0%{transform:rotate(0)} 35%{transform:rotate(20deg)} 70%{transform:rotate(-3deg)} 100%{transform:rotate(0)} }
          @keyframes a-nod { 0%,100%{transform:rotate(0)} 50%{transform:rotate(-4deg)} }
          @keyframes a-shake { 0%{transform:translate(0)} 25%{transform:translate(2px,0)} 50%{transform:translate(-2px,0)} 75%{transform:translate(1px,0)} 100%{transform:translate(0)} }
          @keyframes a-wave { 0%,100%{transform:rotate(-3deg)} 50%{transform:rotate(14deg)} }
        `}</style>

        {/* 报告纸 */}
        <g ref={reportRef} style={{ display: 'none' }}>
          <rect x="45" y="22" width="12" height="16" fill="#fff" stroke="#000" strokeWidth="1"/>
          <rect x="47" y="25" width="8"  height="1" fill="#e44"/>
          <rect x="47" y="27" width="8"  height="1" fill="#e44"/>
          <rect x="47" y="29" width="6"  height="1" fill="#e44"/>
          <rect x="47" y="31" width="8"  height="1" fill="#e44"/>
        </g>

        {/* 汗滴 */}
        <g ref={sweatRef} style={{ display: 'none' }}>
          <rect x="50" y="14" width="2" height="3" fill="#88ccff"/>
          <rect x="51" y="15" width="2" height="3" fill="#88ccff"/>
          <rect x="51" y="16" width="1" height="2" fill="#88ccff"/>
        </g>

        <g className={`body-g ${ANIM_CLASS[status] ?? ''}`}>
          {/* 后腿 */}
          <g className="leg-r">
            <rect x="42" y="58" width="4" height="10" fill="#c09050"/>
            <rect x="41" y="67" width="6" height="3"  fill="#8a6030"/>
          </g>
          {/* 前腿 */}
          <g className="leg-l">
            <rect x="28" y="58" width="4" height="10" fill="#d4a96a"/>
            <rect x="27" y="67" width="6" height="3"  fill="#a07040"/>
          </g>

          {/* 白大褂 */}
          <rect x="22" y="43" width="24" height="19" fill="#f5f5f5"/>
          <rect x="21" y="43" width="26" height="2"  fill="#e8e8e8"/>
          <rect x="21" y="42" width="1"  height="2"  fill="#ddd"/>
          <rect x="46" y="42" width="1"  height="2"  fill="#ddd"/>
          <rect x="33" y="47" width="1" height="1" fill="#bbb"/>
          <rect x="33" y="50" width="1" height="1" fill="#bbb"/>
          <rect x="33" y="53" width="1" height="1" fill="#bbb"/>
          <rect x="38" y="48" width="5"  height="4"  fill="#eee"/>
          <rect x="38" y="48" width="5"  height="1"  fill="#ddd"/>
          <rect x="41" y="45" width="1"  height="3"  fill="#333"/>
          <rect x="41" y="47" width="1"  height="2"  fill="#c44"/>

          {/* 左臂 */}
          <g className="arm-l">
            <rect x="17" y="44" width="4" height="10" fill="#d4a96a"/>
            <rect x="17" y="43" width="4" height="3"  fill="#c8a46e"/>
          </g>
          {/* 右臂 */}
          <g className="arm-r">
            <rect x="45" y="44" width="4" height="10" fill="#d4a96a"/>
            <rect x="45" y="43" width="4" height="3"  fill="#c8a46e"/>
          </g>

          {/* 脖子 */}
          <rect x="28" y="37" width="10" height="8" fill="#d4a96a"/>

          {/* 鬃毛 */}
          <rect x="36" y="10" width="2" height="4"  fill="#5a3a1a"/>
          <rect x="37" y="12" width="2" height="4"  fill="#5a3a1a"/>
          <rect x="37" y="16" width="2" height="4"  fill="#5a3a1a"/>
          <rect x="37" y="20" width="2" height="5"  fill="#5a3a1a"/>
          <rect x="37" y="25" width="2" height="5"  fill="#5a3a1a"/>
          <rect x="37" y="30" width="2" height="5"  fill="#5a3a1a"/>

          {/* 头部 */}
          <g className="head-g">
            <rect x="19" y="2"  width="5" height="8"  fill="#c8a46e"/>
            <rect x="20" y="3"  width="3" height="5"  fill="#e8c090"/>
            <rect x="40" y="2"  width="5" height="8"  fill="#c8a46e"/>
            <rect x="41" y="3"  width="3" height="5"  fill="#e8c090"/>
            <rect x="18" y="9"  width="28" height="4"  fill="#d4a96a"/>
            <rect x="16" y="13" width="32" height="12" fill="#d4a96a"/>
            <rect x="24" y="25" width="16" height="4"  fill="#d4a96a"/>
            <rect x="20" y="28" width="24" height="8"  fill="#c09050"/>
            <rect x="24" y="32" width="3" height="2"  fill="#7a5030"/>
            <rect x="37" y="32" width="3" height="2"  fill="#7a5030"/>
            <rect ref={mouthRef} x="28" y="35" width="8" height="1" fill="#6a4030"/>
            <rect ref={sockLRef} x="18" y="15" width="7" height="6" fill="#1a1a1a"/>
            <rect x="19" y="16" width="5" height="4" fill="#f0f0f0"/>
            <rect ref={sockRRef} x="39" y="15" width="7" height="6" fill="#1a1a1a"/>
            <rect x="40" y="16" width="5" height="4" fill="#f0f0f0"/>
            <rect ref={browLRef} x="17" y="13" width="7" height="2" fill="#5a3a1a"/>
            <rect ref={browRRef} x="40" y="13" width="7" height="2" fill="#5a3a1a"/>
            <rect x="17" y="19" width="1" height="6"  fill="#555"/>
            <rect x="17" y="24" width="8" height="1"  fill="#555"/>
            <rect x="24" y="20" width="1" height="7"  fill="#555"/>
            <rect x="22" y="26" width="5" height="3"  fill="#666"/>
            <rect x="23" y="27" width="3" height="1"  fill="#999"/>
            <rect x="15" y="23" width="4" height="2" fill="#e07070" opacity=".3"/>
            <rect x="45" y="23" width="4" height="2" fill="#e07070" opacity=".3"/>
          </g>

          {/* 瞳孔（在 head-g 外面） */}
          <g ref={plRef}>
            <rect x="-2" y="-2" width="3" height="3" fill="#1a1a1a"/>
            <rect x="-1" y="-1" width="1" height="1" fill="#fff"/>
          </g>
          <g ref={prRef}>
            <rect x="-2" y="-2" width="3" height="3" fill="#1a1a1a"/>
            <rect x="-1" y="-1" width="1" height="1" fill="#fff"/>
          </g>
        </g>

        {/* 光晕 */}
        <rect ref={glowRef} x="4" y="0" width="56" height="72" fill="none" stroke="transparent" strokeWidth="1" opacity="0"/>
      </svg>

      <span className={`px-3 py-1 text-xs font-black uppercase tracking-widest border-2 border-black ${STATUS_CLASS[status]}`}>
        {STATUS_TEXT[status]}
      </span>
    </div>
  )
}
