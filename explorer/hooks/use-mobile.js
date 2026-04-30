import * as React from "react"

import {
  CAD_WORKSPACE_MOBILE_MEDIA_QUERY,
  isCadWorkspaceDesktopViewport
} from "../lib/workbench/breakpoints.js"

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(CAD_WORKSPACE_MOBILE_MEDIA_QUERY)
    const onChange = () => {
      setIsMobile(!isCadWorkspaceDesktopViewport(window.innerWidth))
    }
    mql.addEventListener("change", onChange)
    setIsMobile(!isCadWorkspaceDesktopViewport(window.innerWidth))
    return () => mql.removeEventListener("change", onChange);
  }, [])

  return !!isMobile
}
