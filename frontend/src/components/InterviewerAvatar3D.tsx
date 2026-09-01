"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Loader2, AlertCircle } from "lucide-react";

interface InterviewerAvatar3DProps {
  voiceState: string;
  audioLevel?: number;
  analyserNode?: AnalyserNode | null;
  interviewerName?: string;
}

export const InterviewerAvatar3D: React.FC<InterviewerAvatar3DProps> = ({
  voiceState,
  audioLevel = 0,
  analyserNode = null,
  interviewerName = "AI Technical Interviewer"
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // References for Three.js render loop & morph target control
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const animFrameIdRef = useRef<number | null>(null);
  const headMeshRef = useRef<THREE.SkinnedMesh | null>(null);
  const morphTargetsRef = useRef<{ [name: string]: number }>({});
  const headBoneRef = useRef<THREE.Bone | null>(null);
  const spineBoneRef = useRef<THREE.Bone | null>(null);
  const initialHeadRotationRef = useRef<THREE.Euler>(new THREE.Euler());
  const initialSpinePositionRef = useRef<THREE.Vector3>(new THREE.Vector3());

  // Blinking & Animation timers
  const lastBlinkTimeRef = useRef<number>(0);
  const nextBlinkIntervalRef = useRef<number>(3.2);
  const isBlinkingRef = useRef<boolean>(false);
  const blinkProgressRef = useRef<number>(0);

  // Smooth audio amplitude tracker
  const smoothAmpRef = useRef<number>(0);

  useEffect(() => {
    let isMounted = true;
    const container = containerRef.current;
    if (!container) return;

    // Check WebGL availability
    const testCanvas = document.createElement("canvas");
    const gl =
      testCanvas.getContext("webgl2") ||
      testCanvas.getContext("webgl") ||
      testCanvas.getContext("experimental-webgl");
    if (!gl) {
      setLoadError("3D interviewer unavailable: WebGL not supported in this browser.");
      setLoading(false);
      return;
    }

    // 1. Scene Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0c111d");
    sceneRef.current = scene;

    // 2. Camera Setup (framed on rpm_halfbody head and upper torso with portrait FOV)
    const initialRect = container.getBoundingClientRect();
    const width = initialRect.width || container.clientWidth || 640;
    const height = initialRect.height || container.clientHeight || 440;
    const camera = new THREE.PerspectiveCamera(30, width / Math.max(1, height), 0.05, 50);
    // Ideal upper-body portrait framing for 3D technical interviewer
    camera.position.set(0, 0.58, 0.62);
    camera.lookAt(new THREE.Vector3(0, 0.56, 0));

    // 3. Renderer Setup
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance"
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    rendererRef.current = renderer;

    // Clean container before appending
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    container.appendChild(renderer.domElement);

    // 4. Professional Studio Lighting Setup (360 Omni + 3-Point Studio Lights)
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 2.2);
    hemiLight.position.set(0, 2, 0);
    scene.add(hemiLight);

    const ambientLight = new THREE.AmbientLight(0xffffff, 1.8);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xfff8f0, 2.5);
    keyLight.position.set(1.0, 1.8, 1.5);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xdbeafe, 1.6);
    fillLight.position.set(-1.2, 1.2, 1.2);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0x818cf8, 2.0);
    rimLight.position.set(0, 1.8, -1.2);
    scene.add(rimLight);

    const frontLight = new THREE.PointLight(0xffffff, 1.2, 4.0);
    frontLight.position.set(0, 0.55, 0.9);
    scene.add(frontLight);

    // 5. Load GLTF / GLB Avatar (rpm_halfbody.glb)
    const loader = new GLTFLoader();
    const avatarUrl = "/avatars/rpm_halfbody.glb";

    loader.load(
      avatarUrl,
      (gltf) => {
        if (!isMounted) return;

        const model = gltf.scene;
        // Strictly uniform scale to prevent any stretching
        model.scale.setScalar(1.0);
        model.position.set(0, 0, 0);
        scene.add(model);

        // Traverse model to optimize materials, disable frustum culling, and link morph targets
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            child.frustumCulled = false; // Never cull avatar mesh during skeletal rotation
            child.castShadow = true;
            child.receiveShadow = true;

            const mesh = child as THREE.Mesh;
            if (mesh.material) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m) => {
                  m.side = THREE.DoubleSide;
                  m.needsUpdate = true;
                });
              } else {
                mesh.material.side = THREE.DoubleSide;
                mesh.material.needsUpdate = true;
              }
            }
          }

          if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
            const skinnedMesh = child as THREE.SkinnedMesh;
            if (skinnedMesh.morphTargetDictionary && skinnedMesh.morphTargetInfluences) {
              headMeshRef.current = skinnedMesh;
              morphTargetsRef.current = skinnedMesh.morphTargetDictionary;
            }
          }

          if ((child as THREE.Bone).isBone) {
            const bone = child as THREE.Bone;
            const bName = (bone.name || "").toLowerCase();
            if (bName === "head" || bName.includes("head")) {
              headBoneRef.current = bone;
              initialHeadRotationRef.current = bone.rotation.clone();
            } else if (bName === "spine" || bName.includes("spine")) {
              spineBoneRef.current = bone;
              initialSpinePositionRef.current = bone.position.clone();
            }
          }
        });

        model.updateMatrixWorld(true);
        setLoading(false);
      },
      undefined,
      (error) => {
        console.error("GLTFLoader error loading 3D avatar:", error);
        if (isMounted) {
          setLoadError("3D interviewer unavailable: failed to load rpm_halfbody.glb");
          setLoading(false);
        }
      }
    );

    // 6. Handle Container Resize dynamically with ResizeObserver
    const updateDimensions = () => {
      if (!container || !rendererRef.current) return;
      const rect = container.getBoundingClientRect();
      const w = rect.width || container.clientWidth || 640;
      const h = rect.height || container.clientHeight || 440;
      if (w > 0 && h > 0) {
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        rendererRef.current.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        rendererRef.current.setSize(w, h, false);
      }
    };

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        updateDimensions();
      });
      resizeObserver.observe(container);
    }
    window.addEventListener("resize", updateDimensions);

    // 7. Render Loop with Audio-Driven Lip Sync and Idle Motion
    const clock = new THREE.Clock();
    const freqData = new Uint8Array(64);

    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate);

      const elapsedTime = clock.getElapsedTime();

      // A. Audio Level & Frequency Analysis
      let currentAmp = audioLevel / 100;
      if (analyserNode && voiceState === "ai_speaking") {
        try {
          analyserNode.getByteFrequencyData(freqData);
          let sum = 0;
          for (let i = 0; i < 32; i++) sum += freqData[i];
          const avg = sum / 32;
          currentAmp = Math.max(currentAmp, avg / 125);
        } catch (e) {}
      }

      // Smooth amplitude dampening
      smoothAmpRef.current = THREE.MathUtils.lerp(smoothAmpRef.current, currentAmp, 0.35);

      // B. Lip Sync Morph Targets Modulation
      if (headMeshRef.current && headMeshRef.current.morphTargetInfluences) {
        const influences = headMeshRef.current.morphTargetInfluences;
        const dict = morphTargetsRef.current;

        const isSpeaking = voiceState === "ai_speaking";
        const amp = isSpeaking ? smoothAmpRef.current : 0;

        // Dynamic mouth opening with natural speech jitter
        const speechOsc = isSpeaking ? (Math.sin(elapsedTime * 18) * 0.12 + Math.cos(elapsedTime * 24) * 0.08) : 0;
        const targetMouthOpen = isSpeaking ? Math.min(1.0, Math.max(0.0, amp * 1.2 + speechOsc)) : 0;

        // Apply to mouthOpen / jawOpen
        if (dict["mouthOpen"] !== undefined) {
          influences[dict["mouthOpen"]] = THREE.MathUtils.lerp(influences[dict["mouthOpen"]], targetMouthOpen, 0.4);
        }
        if (dict["jawOpen"] !== undefined) {
          influences[dict["jawOpen"]] = THREE.MathUtils.lerp(influences[dict["jawOpen"]], targetMouthOpen * 0.65, 0.4);
        }

        // Apply to speech visemes for realistic phonetic motion
        const visemeAA = isSpeaking ? Math.min(0.85, Math.max(0, Math.sin(elapsedTime * 13) * amp * 0.9)) : 0;
        const visemeE = isSpeaking ? Math.min(0.65, Math.max(0, Math.cos(elapsedTime * 15) * amp * 0.7)) : 0;
        const visemeO = isSpeaking ? Math.min(0.75, Math.max(0, Math.sin(elapsedTime * 10) * amp * 0.8)) : 0;
        const visemeI = isSpeaking ? Math.min(0.6, Math.max(0, Math.cos(elapsedTime * 12) * amp * 0.6)) : 0;

        if (dict["viseme_aa"] !== undefined) influences[dict["viseme_aa"]] = THREE.MathUtils.lerp(influences[dict["viseme_aa"]], visemeAA, 0.35);
        if (dict["viseme_E"] !== undefined) influences[dict["viseme_E"]] = THREE.MathUtils.lerp(influences[dict["viseme_E"]], visemeE, 0.35);
        if (dict["viseme_O"] !== undefined) influences[dict["viseme_O"]] = THREE.MathUtils.lerp(influences[dict["viseme_O"]], visemeO, 0.35);
        if (dict["viseme_I"] !== undefined) influences[dict["viseme_I"]] = THREE.MathUtils.lerp(influences[dict["viseme_I"]], visemeI, 0.35);

        // Friendly slight professional smile
        if (dict["mouthSmile"] !== undefined) {
          influences[dict["mouthSmile"]] = 0.15;
        }

        // C. Natural Eye Blinking Logic
        if (!isBlinkingRef.current && elapsedTime - lastBlinkTimeRef.current > nextBlinkIntervalRef.current) {
          isBlinkingRef.current = true;
          blinkProgressRef.current = 0;
        }

        if (isBlinkingRef.current) {
          blinkProgressRef.current += 14 * 0.016;
          let blinkWeight = 0;
          if (blinkProgressRef.current < 0.5) {
            blinkWeight = blinkProgressRef.current * 2;
          } else if (blinkProgressRef.current < 1.0) {
            blinkWeight = (1.0 - blinkProgressRef.current) * 2;
          } else {
            isBlinkingRef.current = false;
            lastBlinkTimeRef.current = elapsedTime;
            nextBlinkIntervalRef.current = 2.8 + Math.random() * 3.2; // 2.8 to 6 sec random blink interval
          }

          if (dict["eyesClosed"] !== undefined) influences[dict["eyesClosed"]] = blinkWeight;
          if (dict["eyeBlinkLeft"] !== undefined) influences[dict["eyeBlinkLeft"]] = blinkWeight;
          if (dict["eyeBlinkRight"] !== undefined) influences[dict["eyeBlinkRight"]] = blinkWeight;
        }
      }

      // D. Subtle Human Idle Motion & Breathing
      const breath = Math.sin(elapsedTime * 1.6) * 0.005;
      const headPitch = (voiceState === "listening" || voiceState === "candidate_speaking")
        ? 0.03 + Math.sin(elapsedTime * 0.8) * 0.008  // Attentive listening forward tilt
        : Math.sin(elapsedTime * 1.1) * 0.008;

      const headYaw = Math.cos(elapsedTime * 0.5) * 0.012;

      if (headBoneRef.current) {
        headBoneRef.current.rotation.x = initialHeadRotationRef.current.x + headPitch;
        headBoneRef.current.rotation.y = initialHeadRotationRef.current.y + headYaw;
        headBoneRef.current.rotation.z = initialHeadRotationRef.current.z + Math.sin(elapsedTime * 0.7) * 0.005;
      }
      if (spineBoneRef.current) {
        spineBoneRef.current.position.y = initialSpinePositionRef.current.y + breath;
      }

      // Render Scene
      renderer.render(scene, camera);
    };

    animate();

    // Cleanup on unmount
    return () => {
      isMounted = false;
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      window.removeEventListener("resize", updateDimensions);
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
      if (rendererRef.current && rendererRef.current.domElement) {
        if (container.contains(rendererRef.current.domElement)) {
          container.removeChild(rendererRef.current.domElement);
        }
        rendererRef.current.dispose();
      }
    };
  }, []);

  if (loadError) {
    return (
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#090d16",
          color: "#f87171",
          padding: "2rem",
          textAlign: "center"
        }}
      >
        <AlertCircle size={36} style={{ marginBottom: "0.75rem", opacity: 0.85 }} />
        <p style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "0.4rem" }}>3D Interviewer Unavailable</p>
        <p style={{ fontSize: "0.82rem", color: "#94a3b8", maxWidth: "360px" }}>{loadError}</p>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        backgroundColor: "#0c111d",
        display: "block"
      }}
    >
      {/* 3D WebGL Canvas Container */}
      <div
        ref={containerRef}
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          position: "absolute",
          inset: 0
        }}
      />

      {/* Loading Spinner during initial 3D GLB load */}
      {loading && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#0c111d",
            color: "#ffffff",
            zIndex: 10
          }}
        >
          <Loader2 className="animate-spin" size={34} color="#6366f1" style={{ marginBottom: "0.75rem" }} />
          <span style={{ fontSize: "0.88rem", color: "#94a3b8", fontWeight: 600 }}>
            Loading 3D Interviewer Avatar...
          </span>
        </div>
      )}
    </div>
  );
};
