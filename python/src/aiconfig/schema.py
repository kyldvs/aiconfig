import warnings
from typing import Any, Dict, List, Literal, Optional, Union

from aiconfig.util.config_utils import extract_override_settings
from pydantic import BaseModel

# Pydantic doesn't handle circular type references very well, TODO: handle this better than defining as type Any
# JSONObject represents a JSON object as a dictionary with string keys and JSONValue values
JSONObject = Dict[str, Any]
# InferenceSettings represents settings for model inference as a JSON object
InferenceSettings = JSONObject


class OutputDataWithStringValue(BaseModel):
    """
    This represents the output content that is storied as a string, but we use
    both the `kind` field here and the `mime_type` in ExecuteResult to convert
    the string into the output format we want.
    """

    kind: Literal["file_uri", "base64"]
    value: str


class FunctionCallData(BaseModel):
    """
    Function call data reprsenting a single function call
    """

    arguments: str
    """
    The arguments to call the function with, as generated by the model in JSON
    format. Note that the model does not always generate valid JSON, and may
    hallucinate parameters not defined by your function schema. Validate the
    arguments in your code before calling your function.
    """

    name: str
    """The name of the function to call."""

    class Config:
        extra = "allow"


class ToolCallData(BaseModel):
    """
    Generic tool call data
    """

    id: Optional[str]
    """
    Note: the `id` field is non-optional in OpenAI but we're keeping
    it optional for practical purposes. See:
    https://github.com/lastmile-ai/aiconfig/pull/636#discussion_r1437087325
    """

    function: FunctionCallData
    type: Literal["function"]


class OutputDataWithToolCallsValue(BaseModel):
    """
    This based off of ChatCompletionMessageToolCall from openai.types.chat
    and is used for general tool calls.
    """

    kind: Literal["tool_calls"]
    value: List[ToolCallData]


OutputDataWithValue = Union[
    OutputDataWithStringValue,
    OutputDataWithToolCallsValue,
]


class ExecuteResult(BaseModel):
    """
    ExecuteResult represents the result of executing a prompt.
    """

    # Type of output
    output_type: Literal["execute_result"]
    # nth choice.
    execution_count: Union[int, None] = None
    # The result of the executing prompt.
    data: Union[OutputDataWithValue, str, Any]
    # The MIME type of the result. If not specified, the MIME type will be assumed to be plain text.
    mime_type: Optional[str] = None
    # Output metadata
    metadata: Dict[str, Any]


class Error(BaseModel):
    """
    Error represents an error that occurred while executing a prompt.
    """

    # Type of output
    output_type: Literal["error"]
    # The name of the error
    ename: str
    # The value, or message, of the error
    evalue: str
    # The error's traceback, represented as an array of strings
    traceback: List[str]


# Output can be one of ExecuteResult, ExecuteResult, DisplayData, Stream, or Error
Output = Union[ExecuteResult, Error]


class ModelMetadata(BaseModel):
    # The ID of the model to use.
    name: str
    # Model Inference settings that apply to this prompt.
    settings: Optional[InferenceSettings] = {}


class PromptMetadata(BaseModel):
    # Model name/settings that apply to this prompt
    # These settings override any global model settings that may have been defined in the AIConfig metadata.
    # If this is a string, it is assumed to be the model name.
    # Ift this is undefined, the default model specified in the default_model_property will be used for this Prompt.
    model: Optional[Union[ModelMetadata, str]] = None
    # Tags for this prompt. Tags must be unique, and must not contain commas.
    tags: Optional[List[str]] = None
    # Parameter definitions that are accessible to this prompt
    parameters: Optional[JSONObject] = {}

    class Config:
        extra = "allow"


class Attachment(BaseModel):
    """
    Attachment used to pass data in PromptInput for non-text inputs (ex: image, audio)
    """

    # The data representing the attachment
    data: Any
    # The MIME type of the result. If not specified, the MIME type will be assumed to be text/plain
    mime_type: Optional[str] = None
    # Output metadata
    metadata: Optional[Dict[str, Any]] = None


class PromptInput(BaseModel):
    # Attachments can be used to pass in non-text inputs (ex: image, audio)
    attachments: Optional[List[Attachment]] = None

    # Freeform data for the overall prompt input (ex: document answering question
    # requires both images (attachments) and question (data))
    data: Optional[Any] = None

    class Config:
        extra = "allow"


class Prompt(BaseModel):
    # A unique identifier for the prompt. This is used to reference the prompt in other parts of the AIConfig (such as other prompts)
    name: str
    # The prompt string, or a more complex prompt object
    input: Union[str, PromptInput]
    # Metadata for the prompt
    metadata: Optional[PromptMetadata] = None
    # Execution, display, or stream outputs (currently a work-in-progress)
    outputs: Optional[List[Output]] = []

    class Config:
        extra = "allow"

    def add_output(self, output: Output):
        self.outputs.append(output)

    def get_raw_prompt_from_config(self):
        """Gets raw prompt from config"""
        if isinstance(self.input, str):
            return self.input
        else:
            return self.input.prompt


class SchemaVersion(BaseModel):
    major: int
    minor: int


class ConfigMetadata(BaseModel):
    # Parameter definitions that are accessible to all prompts in this AIConfig.
    # These parameters can be referenced in the prompts using handlebars syntax.
    # For more information, see https://handlebarsjs.com/guide/#basic-usage.
    parameters: Optional[JSONObject] = {}
    # Globally defined model settings. Any prompts that use these models will have these settings applied by default,
    # unless they override them with their own model settings.
    models: Optional[Dict[str, InferenceSettings]] = {}
    # Default model to use for prompts that do not specify a model.
    default_model: Optional[str] = None
    # Model ID to ModelParser ID mapping.
    # This is useful if you want to use a custom ModelParser for a model, or if a single ModelParser can handle multiple models.
    # Key is Model ID , Value is ModelParserID
    model_parsers: Optional[Dict[str, str]] = None

    class Config:
        extra = "allow"


class AIConfig(BaseModel):
    """
    AIConfig schema, latest version. For older versions, see AIConfigV*
    """

    # Friendly name descriptor for the AIConfig. Could default to the filename if not specified.
    name: str
    # The version of the AIConfig schema
    schema_version: Union[SchemaVersion, Literal["v1", "latest"]] = "latest"
    # Root-level metadata that applies to the entire AIConfig
    metadata: ConfigMetadata
    # Description of the AIConfig. If you have a collection of different AIConfigs, this may be used for dynamic prompt routing.
    description: Optional[str] = ""
    # An Array of prompts that make up the AIConfig
    prompts: List[Prompt] = []
    # An index of prompts by name, constructed during post-initialization.
    prompt_index: Dict[str, Prompt] = {}

    class Config:
        extra = "allow"

    def model_post_init(self, __context):
        """Post init hook for model"""
        self.prompt_index = {prompt.name: prompt for prompt in self.prompts}

    def set_name(self, name: str):
        """
        Sets the name of the AIConfig

        Args:
            name (str): The name of the AIConfig
        """
        self.name = name

    def set_description(self, description: str):
        """
        Sets the description of the AIConfig

        Args:
            description (str): The description of the AIConfig
        """
        self.description = description

    def add_model(self, model_name: str, model_settings: InferenceSettings):
        """
        Adds model settings to config level metadata
        """
        if model_name in self.metadata.models:
            raise Exception(f"Model '{model_name}' already exists. Use `update_model()`.")
        self.metadata.models[model_name] = model_settings

    def delete_model(self, model_name: str):
        """
        Deletes model settings from config level metadata
        """
        if model_name not in self.metadata.models:
            raise Exception(f"Model '{model_name}' does not exist.")
        del self.metadata.models[model_name]

    def get_model_name(self, prompt: Union[str, Prompt]) -> str:
        """
        Extracts the model ID from the prompt.

        Args:
            prompt: Either the name of the prompt or a prompt object.

        Returns:
            str: Name of the model used by the prompt.
        """
        if isinstance(prompt, str):
            prompt = self.prompt_index[prompt]
        if not prompt:
            raise Exception(f"Prompt '{prompt}' not found in config.")

        if not prompt.metadata or not prompt.metadata.model:
            # If the prompt doesn't have a model, use the default model
            default_model = self.metadata.default_model
            if not default_model:
                raise Exception(f"No model specified in AIConfig metadata, prompt {prompt.name} does not specify a model.")
            return default_model
        if isinstance(prompt.metadata.model, str):
            return prompt.metadata.model
        else:
            # Expect a ModelMetadata object
            return prompt.metadata.model.name

    def set_default_model(self, model_name: Union[str, None]):
        """
        Sets the model to use for all prompts by default in the AIConfig. Set to None to delete the default model.

        Args:
            model_name (str): The name of the default model.
        """
        self.metadata.default_model = model_name

    def get_default_model(self) -> Union[str, None]:
        """
        Returns the default model for the AIConfig.
        """
        return self.metadata.default_model

    def set_model_parser(self, model_name: str, model_parser_id: Union[str, None]):
        """
        Adds a model name : model parser ID mapping to the AIConfig metadata. This model parser will be used to parse Promps in the AIConfig that use the given model.

        Args:
            model_name (str): The name of the model to set the parser.
            model_parser_id (str): The ID of the model parser to use for the mode. If None, the model parser for the model will be removed.
        """
        if not self.metadata.model_parsers:
            self.metadata.model_parsers = {}

        self.metadata.model_parsers[model_name] = model_parser_id

    def get_metadata(self, prompt_name: Optional[str] = None):
        """
        Gets the metadata for a prompt. If no prompt is specified, gets the global metadata.

        Args:
            prompt_name (str, optional): The name of the prompt. Defaults to None.

        Returns:
            PromptMetadata: The metadata for the prompt.
        """
        if prompt_name:
            if prompt_name not in self.prompt_index:
                raise IndexError(f"Prompt '{prompt_name}' not found in config.")
            return self.prompt_index[prompt_name].metadata
        else:
            return self.metadata

    def get_parameters(
        self,
        prompt_or_prompt_name: Optional[str | Prompt] = None,
    ) -> JSONObject:
        """
        Get the parameters for a prompt, using the global parameters if
        needed.

        Args:
            prompt_or_prompt_name Optional[str | Prompt]: The name of the
                prompt or the prompt object. If not specified, use the
                global parameters.
        """
        prompt = prompt_or_prompt_name
        if isinstance(prompt_or_prompt_name, str):
            if prompt_or_prompt_name not in self.prompt_index:
                raise IndexError(f"Prompt '{prompt_or_prompt_name}' not found in config, available prompts are:\n {list(self.prompt_index.keys())}")
            prompt = self.prompt_index[prompt_or_prompt_name]

        assert prompt is None or isinstance(prompt, Prompt)
        if prompt is None or not prompt.metadata or not prompt.metadata.parameters:
            return self.get_global_parameters()

        return self.get_prompt_parameters(prompt)

    # pylint: disable=W0102
    def get_global_parameters(
        self,
        default_return_value: JSONObject = {},
    ) -> JSONObject:
        """
        Get the global parameters for the AIConfig. If they're not defined,
        return a default value ({} unless overridden)

        Args:
            default_return_value JSONObject - Default value to return if
                global parameters are not defined.
        """
        return self._get_global_parameters_exact() or default_return_value

    # pylint: enable=W0102

    def _get_global_parameters_exact(self) -> JSONObject | None:
        """
        Get the global parameters for the AIConfig. This should be the
        the explicit value (ie: if parameters is None, return None, not {})
        """
        return self.metadata.parameters

    # pylint: disable=W0102
    def get_prompt_parameters(
        self,
        prompt: Prompt,
        default_return_value: JSONObject = {},
    ) -> JSONObject:
        """
        Get the prompt's local parameters. If they're not defined,
        return a default value ({} unless overridden)

        Args:
            default_return_value JSONObject - Default value to return if
                prompt parameters are not defined.
        """
        return self._get_prompt_parameters_exact(prompt) or default_return_value

    # pylint: enable=W0102

    def _get_prompt_parameters_exact(
        self,
        prompt: Prompt,
    ) -> JSONObject | None:
        """
        Get the global parameters for the AIConfig. This should be the
        the explicit value (ie: if parameters is None, return None, not {})
        """
        if not prompt.metadata:
            return prompt.metadata
        return prompt.metadata.parameters

    def set_parameter(self, parameter_name: str, parameter_value: Union[str, JSONObject], prompt_name: Optional[str] = None):
        """
        Sets a parameter in the AI configuration metadata. If a prompt_name
        is specified, it adds the parameter to a specific prompt's metadata
        in the AI configuration. Otherwise, it adds the parameter to the
        global metadata.

        Args:
            parameter_name (str): The name of the parameter.
            parameter_value: The value of the parameter. It can be more than
                just a string. It can be a string or a JSON object. For
                example:
                    {
                    person: {
                        firstname: "john",
                        lastname: "smith",
                        },
                    }
                Using the parameter in a prompt with handlebars syntax would
                look like this:
                    "{{person.firstname}} {{person.lastname}}"
            prompt_name (str, optional): The name of the prompt to add the
                parameter to. Defaults to None.
        """
        target_metadata = self.get_metadata(prompt_name)
        if not target_metadata:
            # Technically this check is not needed since the metadata is a
            # required field in Config while it is not required in Prompt.
            # Therefore, if it's not defined, we can infer that it should
            # be a PromptMetadata type, but this is just good robustness
            # in case we ever change our schema in the future
            if prompt_name:
                prompt = self.get_prompt(prompt_name)
                # check next line not needed since it's already assumed
                # we got here because target_metadata is None, just being
                # extra safe
                if not prompt.metadata:
                    target_metadata = PromptMetadata(parameters={})
                    prompt.metadata = target_metadata
            else:
                if not self.metadata:
                    target_metadata = ConfigMetadata()
                    self.metadata = target_metadata

        assert target_metadata is not None
        if target_metadata.parameters is None:
            target_metadata.parameters = {}
        target_metadata.parameters[parameter_name] = parameter_value

    def set_parameters(self, parameters: JSONObject, prompt_name: Optional[str] = None) -> None:
        """
        Set the entire parameters dict for either a prompt (if specified)
        or the AIConfig (if prompt is not specified). It overwrites whatever
        was previously stored as parameters for the prompt or AIConfig.

        Args:
            parameters (JSONObject): The entire set of parameters. Ex:
                {
                    "city": "New York",
                    "sort_by": "geographical location",
                }
                In this example, we call `set_parameter` twice:
                    1) set_parameter("city", "New York", prompt_name)
                    2) set_parameter("sort_by", "geographical location", prompt_name)

            prompt_name (str, optional): The name of the prompt to add the
                parameters dict to. If none is provided, we update the
                AIConfig-level parameters instead
        """
        # Clear all existing parameters before setting new ones
        parameter_names_to_delete = []
        if prompt_name:
            prompt = self.get_prompt(prompt_name)
            parameter_names_to_delete = list(self.get_prompt_parameters(prompt).keys())
        else:
            parameter_names_to_delete = list(self.get_global_parameters().keys())

        for parameter_name in parameter_names_to_delete:
            self.delete_parameter(parameter_name, prompt_name)

        for parameter_name, parameter_value in parameters.items():
            self.set_parameter(parameter_name, parameter_value, prompt_name)

    def update_parameter(
        self,
        parameter_name: str,
        parameter_value: str,
        prompt_name: Optional[str] = None,
    ):
        """
        Updates a parameter in the AI configuration metadata. If a prompt_name is specified, it updates the parameter
        in a specific prompt's metadata in the AI configuration. Otherwise, it updates the parameter in the global
        metadata. If the parameter doesn't exist, it adds the parameter.

        Args:
            parameter_name (str): The name of the parameter.
            parameter_value (str): The value of the parameter.
            prompt_name (str, optional): The name of the prompt (if applicable). Defaults to None.
        """
        target_metadata = self.get_metadata(prompt_name)
        target_metadata.parameters[parameter_name] = parameter_value

    def delete_parameter(self, parameter_name, prompt_name: Optional[str] = None):
        """
        Removes a parameter from the AI configuration metadata. If a prompt_name is specified, it removes the parameter
        from a particular prompt's metadata in the AI configuration. Else, it removes the parameter from the global
        metadata. If the parameter doesn't exist, do nothing.

        Args:
            parameter_name (str): The name of the parameter.
            prompt_name (str, optional): The name of the prompt to remove the parameter from. Defaults to None.
        """
        target_metadata = self.get_metadata(prompt_name)

        # Remove the parameter if it exists
        if parameter_name in target_metadata.parameters:
            del target_metadata.parameters[parameter_name]
        else:
            scope_suffix = f"prompt '{prompt_name}'" if prompt_name is not None else "current AIConfig-scoped metadata"
            raise KeyError(f"Parameter '{parameter_name}' does not exist for {scope_suffix}.")

    def get_prompt(self, prompt_name: str) -> Prompt:
        """
        Gets a prompt byname from the aiconfig.

        Args:
            prompt_name (str): The name of the prompt to get.

        Returns:
            Prompt: The prompt object.
        """
        if prompt_name not in self.prompt_index:
            raise IndexError("Prompt '{}' not found in config, available prompts are:\n {}".format(prompt_name, list(self.prompt_index.keys())))
        return self.prompt_index[prompt_name]

    def add_prompt(self, prompt_name: str, prompt_data: Prompt, index: int | None = None):
        """
        Adds a prompt to the .aiconfig.

        Args:
            prompt_name (str): The name of the prompt to add.
            prompt_data (Prompt): The prompt object containing the prompt data.
        """
        if prompt_name is None:
            prompt_name = prompt_data.name
        if prompt_name in self.prompt_index:
            raise Exception("Prompt with name {} already exists. Use`update_prompt()`".format(prompt_name))

        prompt_data.name = prompt_name
        self.prompt_index[prompt_name] = prompt_data
        if index is None:
            self.prompts.append(prompt_data)
        else:
            self.prompts.insert(index, prompt_data)

    def update_prompt(self, prompt_name: str, prompt_data: Prompt):
        """
        Given a prompt name and a prompt object, updates the prompt in the .aiconfig.

        Args:
            prompt_name (str): The name of the prompt to update.
            prompt_data (Prompt): The prompt object containing the updated prompt data.
        """
        if prompt_name not in self.prompt_index:
            raise IndexError("Prompt '{}' not found in config, available prompts are:\n {}".format(prompt_name, list(self.prompt_index.keys())))

        self.prompt_index[prompt_name] = prompt_data
        # update prompt list
        for i, prompt in enumerate(self.prompts):
            if prompt.name == prompt_name:
                self.prompts[i] = prompt_data
                del self.prompt_index[prompt_name]
                self.prompt_index[prompt_data.name] = prompt_data
                break

    def delete_prompt(self, prompt_name: str):
        """
        Given a prompt name, deletes the prompt from the .aiconfig.

        Args:
            prompt_name (str): The name of the prompt to delete.
        """
        if prompt_name not in self.prompt_index:
            raise IndexError("Prompt '{}' not found in config, available prompts are:\n {}".format(prompt_name, list(self.prompt_index.keys())))

        del self.prompt_index[prompt_name]
        # remove from prompt list
        self.prompts = [prompt for prompt in self.prompts if prompt.name != prompt_name]

    def get_model_metadata(self, inference_settings: InferenceSettings, model_id: str) -> ModelMetadata:
        """
        Generate a model metadata object based on the provided inference settings

        This function takes the inference settings and the model ID and generates a ModelMetadata object.

        Args:
            inference_settings (InferenceSettings): The inference settings.
            model_id (str): The model id.

        Returns:
            ModelMetadata: The model metadata.
        """

        overriden_settings = extract_override_settings(self, inference_settings, model_id)

        if not overriden_settings:
            model_metadata = ModelMetadata(**{"name": model_id})
        else:
            model_metadata = ModelMetadata(**{"name": model_id, "settings": overriden_settings})
        return model_metadata

    # TODO (rossdan): If we pass in a new model under ModelMetadata, but that model is
    # not already registered to a model parser, we should throw an error and instruct
    # user how to update this in their code or AIConfig. OR we should allow a
    # model_parser_id field to be passed into ModelMetadata and (somehow) find the ID
    # that matches this class and do this automatically with the
    # `update_model_parser_registry_with_config_runtime`` function
    # Tracked in https://github.com/lastmile-ai/aiconfig/issues/503
    def update_model(self, model_name: Optional[str] = None, settings: Optional[InferenceSettings] = None, prompt_name: Optional[str] = None):
        """
        Updates model name and/or settings at the prompt (if specified) or AIConfig level.

        Args:
            name (str): The model name to update.
                - If None: keep existing name for prompt; error for AIConfig.
            settings (dict): The model settings to update.
                - If None: keep existing settings for prompt; keep existing
                  for AIConfig (if model name exists) or create empty settings
            prompt_name (Optional[str]): If specified, the model updatd will
                only be applied to the prompt with the given prompt_name.

        Examples:
            update_model("gpt3", None, "my_prompt")
                --> updates "my_prompt" to use "gpt3" with existing settings
            update_model("gpt3", None)
                --> updates aiconfig model key "gpt3" to use existing
                    settings (empty if model was not previously defined)
            update_model(None, {}, "my_prompt")
                --> updates "my_prompt" to use same model with empty settings
            update_model(None, {})
                --> errors because AiConfig needs a name to know which
                    model to update
            update_model(None, None, "my_prompt")
                --> errors becasue no model name or settings provided
        """
        if model_name is None and settings is None:
            raise ValueError("Cannot update model. Either model name or model settings must be specified.")
        if model_name is None and prompt_name is None:  # Only settings param is set
            raise ValueError(
                """
Cannot update model. There are two things you are trying: \
    1) Update the settings of a prompt \
        Fix: You must pass in a `prompt_name` argument \
    2) Update the settings at the AIConfig-level \
        Fix: You must pass in a `name` for the model you wish \
        to update. AIConfig-level can have multiple models, \
        so without a model name, we don't know which model \
        to set the settings for."
"""
            )

        if prompt_name is not None:
            # We first update the model name, then update the model settings
            if model_name is not None:
                self._update_model_name_for_prompt(model_name, prompt_name)

            if settings is not None:
                self._update_model_settings_for_prompt(settings, prompt_name)
        else:
            if model_name is not None:
                self._update_model_for_aiconfig(model_name, settings)

    def _update_model_name_for_prompt(self, model_name: str, prompt_name: str):
        """
        Updates model name at the prompt. To keep things simplified, at the
        prompt level we are only updating the model name, preserving existing
        settings if they exist, or setting the settings to empty dict. We
        will update the settings in a follow up
        `_update_model_settings_for_prompt()` call. The reason we do is
        to delegate the `settings is None` check inside of `update_model()`
        instead of making this function more complicated.

        If model is not already specified for a prompt, we err on the side of
        passing in the entire ModelMetadata into the prompt, even if there
        are no settings, just becuase this makes it easier to manage for
        future writes in case we want to add model settings later
        (see `_update_model_settings`).

        Args:
            model_name (str): Model name to set
            prompt_name (str): The name of the prompt we want to update
        """
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            raise IndexError(
                f"Cannot update model name of '{model_name}' for prompt '{prompt_name}'. Prompt {prompt_name} does not exist in AIConfig."
            )
        if prompt.metadata is None:
            model_metadata = ModelMetadata(name=model_name, settings={})
            prompt.metadata = PromptMetadata(model=model_metadata)
        elif prompt.metadata.model is None or isinstance(prompt.metadata.model, str):
            prompt.metadata.model = ModelMetadata(name=model_name, settings={})
        else:
            # prompt.metadata.model is a ModelMetadata object
            model_settings: InferenceSettings = prompt.metadata.model.settings or {}
            prompt.metadata.model = ModelMetadata(name=model_name, settings=model_settings)

    def _update_model_settings_for_prompt(self, settings: InferenceSettings, prompt_name: str):
        """
        Updates model name at the prompt level. We do not update at the
        AIConfig level because an AIConfig can have multiple models, so
        without the model name, we don't know which model to update.

        Args:
            settings (InferenceSettings): Model settings to set
            prompt_name (str): The name of the prompt we want to update.
        """
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            raise IndexError(f"Cannot update model settings for prompt '{prompt_name}'. Prompt '{prompt_name}' does not exist in AIConfig.")

        metadata_error_message = f"""
Cannot update model settings for prompt '{prompt_name}' because it does not \
have a model name set for it. Please be sure that a model is set for this \
prompt. You can do this be calling `update_model()` and passing a model name \
as an argument.
"""
        if prompt.metadata is None or prompt.metadata.model is None:
            raise ValueError(metadata_error_message)

        if isinstance(prompt.metadata.model, str):
            model_name = prompt.metadata.model
            prompt.metadata.model = ModelMetadata(name=model_name, settings=settings)
        else:
            prompt.metadata.model.settings = settings

    def _update_model_for_aiconfig(self, model_name: str, settings: Union[InferenceSettings, None], prompt_name: Optional[str] = None):
        """
        Updates model name at the AIConfig level.

        Args:
            model_name (str): Model name to set
            settings (Optional[InferenceSettings]): Model settings to set
                For AI-Config level settings we don't know the old model name
                so can't grab the older settings. If this is None, we will:
                    Case 1: Model name already exists at AIConfig level
                        --> Preserve the existing settings
                    Case 2: Model name is new at AIConfig level
                        --> Create an empty dict
        """
        warning_message = f"""
No prompt name was given to update the model name to '{model_name}'. We are \
assuming this is intentional and are therefore updating the \
AIConfig-level settings. If this is a mistake, please rerun the \
`update_model` function with a specified `prompt_name` argument.
"""
        warnings.warn(warning_message)
        if self.metadata.models is None:
            model_settings = settings or {}
            self.metadata.models = {model_name: model_settings}
        else:
            # If the model name already exists and settings is None,
            # this is essentially a no-op since we are preserving
            # existing settings for that model name
            model_settings = settings or self.metadata.models.get(model_name, {})
            self.metadata.models[model_name] = model_settings

    def set_metadata(self, key: str, value: Any, prompt_name: Optional[str] = None):
        """
        Sets a metadata property in the AIConfig

        Args:
            key (str): The Metadata key.
            value (str): Metadata value. Must be a JSON-serializable object (ie dict, list, str, etc).
            prompt_name (str, optional): If specified, the metadata will only be updated for the prompt with the given name
        """
        if prompt_name:
            prompt = self.get_prompt(prompt_name)
            if not prompt:
                raise IndexError(f"Cannot set metadata property '{key}' for prompt {prompt_name}. Prompt {prompt_name} does not exist in AIConfig.")
            setattr(prompt.metadata, key, value)
        else:
            setattr(self.metadata, key, value)

    def delete_metadata(self, key: str, prompt_name: Optional[str] = None):
        """
        Removes a metadata property in the AIConfig

        Args:
            key (str): The Metadata key.
            prompt_name (str, optional): If specified, the metadata will only be deleted for the prompt with the given name
        """
        if prompt_name:
            prompt = self.get_prompt(prompt_name)
            if not prompt:
                raise IndexError(f"Cannot delete metadata. Prompt '{prompt_name}' not found in config.")
            if hasattr(prompt.metadata, key):
                delattr(prompt.metadata, key)
            else:
                raise KeyError(f"Metadata '{key}' does not exist for Prompt {prompt_name}.")
        else:
            if hasattr(self.metadata, key):
                delattr(self.metadata, key)
            else:
                raise KeyError(f"Metadata '{key}' does not exist in config.")

    # TODO: rename _get_metadata to get_metadata

    def add_output(self, prompt_name: str, output: Output, overwrite: bool = False):
        """
        Add an output to the prompt with the given name in the AIConfig

        Args:
            prompt_name (str): The name of the prompt to add the output to.
            output (Output): The output to add.
            overwrite (bool, optional): Overwrites the existing output if True. Otherwise appends the output to the prompt's output list. Defaults to False.
        """
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            raise IndexError(f"Cannot add output. Prompt '{prompt_name}' not found in config.")
        if not output:
            raise ValueError(f"Cannot add output to prompt '{prompt_name}'. Output is not defined.")
        if overwrite:
            prompt.outputs = [output]
        else:
            prompt.outputs.append(output)

    def add_outputs(self, prompt_name: str, outputs: List[Output], overwrite: bool = False):
        """
        Add multiple outputs to the prompt with the given name in the AIConfig

        Args:
            prompt_name (str): The name of the prompt to add the outputs to.
            outputs (List[Output]): List of outputs to add.
            overwrite (bool, optional): Overwrites the existing output if True. Otherwise appends the outputs to the prompt's output list. Defaults to False.
        """
        prompt = self.get_prompt(prompt_name)
        if not prompt:
            raise IndexError(f"Cannot add outputs. Prompt '{prompt_name}' not found in config.")
        if not outputs:
            raise ValueError(f"Cannot add outputs. No outputs provided for prompt '{prompt_name}'.")
        if overwrite:
            prompt.outputs = outputs
        else:
            prompt.outputs.extend(outputs)

    def delete_output(self, prompt_name: str):
        """
        Deletes the outputs for the prompt with the given prompt_name.

        Args:
            prompt_name (str): The name of the prompt to delete the outputs for.

        Returns:
            List[Output]: The outputs that were deleted.
        """
        prompt = self.get_prompt(prompt_name)
        existing_outputs = prompt.outputs
        prompt.outputs = []

        return existing_outputs

    def get_latest_output(self, prompt: str | Prompt):
        """
        Gets the latest output associated with a prompt.

        Args:
            prompt (str|Prompt): The name of the prompt or the prompt object.
        """
        if isinstance(prompt, str):
            prompt = self.prompt_index[prompt]
        if not prompt.outputs:
            return None
        return prompt.outputs[-1]

    def get_output_text(self, prompt: str | Prompt):
        """
        Gets the string representing the output from a prompt.

        Args:
            prompt (str|Prompt): The name of the prompt or the prompt object.
        """

    """
    Library Helpers
    """

    def get_global_settings(self, model_name: str):
        """
        Gets the global settings for a model.

        Args:
            model_name (str): The name of the model.

        Returns:
            dict: The global settings for the model with the given name. Returns an empty dict if no settings are defined.
        """
        return self.metadata.models.get(model_name, {})


AIConfigV1 = AIConfig
