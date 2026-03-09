export type HomepageLink = {
  label: string;
  to: string;
  variant: "primary" | "secondary";
};

export type BottomCard = {
  label: string;
  title: string;
  description: string;
  to?: string;
  href?: string;
  disabled?: boolean;
  cta: string;
  variant: "primary" | "secondary";
};

export type CodeExample = {
  label: string;
  title: string;
  description: string;
  language: string;
  code: string;
};

export type InstallCta = {
  label: string;
  to: string;
};

export const homepageContent = {
  meta: {
    title: "Cairn SDK",
    description: "Documentation for the Cairn SDK",
  },
  badge: "Build Edge AI Faster | on Arm",
  headline: "Ship Edge AI Apps Faster with Cairn SDK",
  lead: "Cairn SDK gives you a production-minded edge foundation out of the box. Connect to and access peripherals, run inference, and orchestrate event-driven workflows with less setup and less glue code.",
  heroLinks: [
    {
      label: "Start Building",
      to: "/category/getting-started",
      variant: "primary",
    },
    {
      label: "Explore Modules",
      to: "/modules/overview",
      variant: "secondary",
    },
  ] as HomepageLink[],
  installTitle: "Get started in 30 seconds",
  installCommands: [
    "topo clone cairn-sdk https://github.com/Arm-Debug/cairn-sdk",
    "topo deploy --target my_user@my_device",
  ],
  installCta: {
    label: "Your First Program",
    to: "/tutorials/getting-started/your-first-program",
  } as InstallCta,
  codeExamples: {
    eyebrow: "Developer Experience",
    title: "From idea to running code in minutes",
    subtitle:
      "Representative snippets that show the Cairn SDK workflow: connect devices, run inference, and ship event-driven behavior quickly.",
    items: [
      {
        label: "High-level SDK",
        title: "Change cameras. Not performance.",
        description: "Zero copy frames to your application.",
        language: "python",
        code: `from cairn import camera

# Ask for any available camera; Cairn resolves the concrete source.
cam = camera.get(prefer="any")
stream = cam.get_stream(zero_copy=True)

for frame in stream:
    process(frame)`,
      },
      {
        label: "Inference Pipeline",
        title: "Compose AI Bricks Into Real Workflows.",
        description:
          "Grab a frame, run object detection, then act on the detections.",
        language: "python",
        code: `from cairn import camera, inference

cam = camera.get(prefer="any")
frame = next(cam.get_stream(zero_copy=True))

result = inference.run(
    brick="object_detection",
    inputs={"image": frame},
)

for obj in result.objects:
    if obj.label == "person" and obj.confidence > 0.7:
        trigger_alert(frame, obj)`,
      },
      {
        label: "Module API (gRPC + Redis)",
        title: "We know best until you know better.",
        description: "Use redis-py directly when you need raw pub/sub control.",
        language: "python",
        code: `import grpc
import camera_pb2
import camera_pb2_grpc
import redis

channel = grpc.insecure_channel("camera-service:8000")
stub = camera_pb2_grpc.CameraServiceStub(channel)

r = redis.Redis(host="redis", port=6379)
stub.Init(camera_pb2.InitRequest(id="front-camera"))

for msg in stub.StreamFrames(camera_pb2.StreamFramesRequest(id="front-camera")):
    handle_bytes(msg.data)
    r.publish("camera.frames", msg.data)`,
      },
    ] as CodeExample[],
  },
  bottomCards: [
    {
      label: "Starter app",
      title: "Sound-to-Text",
      description:
        "Launch a speech transcription pipeline with a lightweight Python app built on Cairn modules.",
      to: "/tutorials/getting-started/sound-to-text",
      cta: "Try tutorial",
      variant: "secondary",
    },
    {
      label: "Starter app",
      title: "Object Detection",
      description:
        "Stand up an object detection flow that combines camera input, inference, and event publishing.",
      to: "/tutorials/getting-started/object-detection",
      cta: "Try tutorial",
      variant: "secondary",
    },
  ] as BottomCard[],
};
