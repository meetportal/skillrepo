import { Text } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useCallback, useLayoutEffect, useRef, type ComponentProps } from "react";
import { useDelayRender } from "remotion";

export const SyncedText = (props: ComponentProps<typeof Text>) => {
  const { delayRender, continueRender } = useDelayRender();
  const pending = useRef<number | null>(null);
  const advance = useThree((state) => state.advance);
  const release = useCallback(() => {
    if (pending.current !== null) {
      advance(performance.now());
      continueRender(pending.current);
      pending.current = null;
    }
  }, [continueRender, advance]);
  useLayoutEffect(() => {
    pending.current = delayRender("troika text glyphs");
    return release;
  }, [delayRender, release]);
  return <Text {...props} onSync={release} />;
};
