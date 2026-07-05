// 花磚 SVG pattern（可重上色，跟 CSS 變數）。
// HzDefs 只需喺 App 掛一次；StarBg 做 Login 滿版；DiamondBand 做內頁分隔／底欄。

export function HzDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        <pattern id="hz-star" width="52" height="52" patternUnits="userSpaceOnUse">
          <rect width="52" height="52" style={{ fill: 'var(--cream)' }} />
          <g transform="translate(26,26)">
            <rect x="-12" y="-12" width="24" height="24" style={{ fill: 'var(--brick)' }} />
            <rect x="-12" y="-12" width="24" height="24" transform="rotate(45)" style={{ fill: 'var(--brick)' }} />
            <circle r="5.5" style={{ fill: 'var(--forest)' }} />
          </g>
          <rect x="-5" y="-5" width="10" height="10" transform="rotate(45 0 0)" style={{ fill: 'var(--forest)' }} />
          <rect x="47" y="47" width="10" height="10" transform="rotate(45 52 52)" style={{ fill: 'var(--forest)' }} />
        </pattern>
        <pattern id="hz-diamond" width="38" height="38" patternUnits="userSpaceOnUse">
          <rect width="38" height="38" style={{ fill: 'var(--cream)' }} />
          <g transform="translate(19,19)">
            <rect x="-11" y="-11" width="22" height="22" transform="rotate(45)" style={{ fill: 'none', stroke: 'var(--brick)', strokeWidth: 2.5 }} />
            <circle r="3" style={{ fill: 'var(--brick)' }} />
          </g>
          <circle cx="0" cy="0" r="2.6" style={{ fill: 'var(--forest)' }} />
          <circle cx="38" cy="0" r="2.6" style={{ fill: 'var(--forest)' }} />
          <circle cx="0" cy="38" r="2.6" style={{ fill: 'var(--forest)' }} />
          <circle cx="38" cy="38" r="2.6" style={{ fill: 'var(--forest)' }} />
        </pattern>
      </defs>
    </svg>
  )
}

export function StarBg() {
  return (
    <svg className="hz-starbg" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="100%" height="100%" fill="url(#hz-star)" />
    </svg>
  )
}

export function DiamondBand({ height = 22, className = '' }) {
  return (
    <svg className={'hz-band ' + className} height={height} width="100%" aria-hidden="true">
      <rect width="100%" height={height} fill="url(#hz-diamond)" />
    </svg>
  )
}
