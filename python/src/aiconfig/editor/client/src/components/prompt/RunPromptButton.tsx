import { Button, createStyles, Flex, Loader, Text } from "@mantine/core";
import { IconPlayerPlayFilled, IconPlayerStop } from "@tabler/icons-react";
import { memo } from "react";

type Props = {
  isRunning?: boolean;
  runPrompt: () => Promise<void>;
  size: "compact" | "full";
};

const useStyles = createStyles(() => ({
  executeButton: {
    borderBottomLeftRadius: 0,
    borderTopLeftRadius: 0,
    borderTopRightRadius: 0,
  },
}));

export default memo(function RunPromptButton({
  runPrompt,
  size,
  isRunning = false,
}: Props) {
  const { classes } = useStyles();
  return (
    <Button
      onClick={runPrompt}
      disabled={isRunning}
      p="xs"
      size="xs"
      fullWidth={size === "full"}
      className={classes.executeButton}
    >
      {isRunning ? (
        <div>
          <Loader
            style={{ position: "absolute", top: 5, left: 8 }}
            size="xs"
            color="white"
          />
          <IconPlayerStop fill="white" size={14} />
        </div>
      ) : (
        <>
          <IconPlayerPlayFilled size="16" />
          {size === "full" && <Text ml="0.5em">Run</Text>}
        </>
      )}
    </Button>
  );
});
