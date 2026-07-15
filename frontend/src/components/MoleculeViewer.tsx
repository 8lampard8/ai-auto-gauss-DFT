import { useEffect, useRef } from 'react'
import type { Molecule } from '../types'

declare global {
  interface Window {
    // 3Dmol.js loaded via CDN in index.html
    $3Dmol?: any
  }
}

export function MoleculeViewer({ molecule }: { molecule: Molecule }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<any>(null)

  // create the viewer once
  useEffect(() => {
    const $3Dmol = window.$3Dmol
    const el = containerRef.current
    if (!$3Dmol || !el) return
    const viewer = $3Dmol.createViewer(el, { antialias: true })
    viewer.setBackgroundColor(0x161a21)
    viewerRef.current = viewer

    const onResize = () => viewer.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      try {
        viewer.clear()
      } catch {
        /* ignore */
      }
      viewerRef.current = null
    }
  }, [])

  // update model when molecule changes
  useEffect(() => {
    const viewer = viewerRef.current
    const $3Dmol = window.$3Dmol
    if (!viewer || !$3Dmol) return
    viewer.clear()
    const data = molecule.molblock || molecule.xyz
    if (!data) return
    const fmt = molecule.molblock ? 'sdf' : 'xyz'
    viewer.addModel(data, fmt)
    viewer.setStyle({}, { stick: { radius: 0.18 }, sphere: { scale: 0.28 } })
    viewer.zoomTo()
    viewer.render()
  }, [molecule])

  return <div className="viewer" ref={containerRef} />
}
