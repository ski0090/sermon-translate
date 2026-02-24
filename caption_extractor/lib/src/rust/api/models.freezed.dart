// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;
/// @nodoc
mixin _$ExtractorEvent {





@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent);
}


@override
int get hashCode => runtimeType.hashCode;

@override
String toString() {
  return 'ExtractorEvent()';
}


}

/// @nodoc
class $ExtractorEventCopyWith<$Res>  {
$ExtractorEventCopyWith(ExtractorEvent _, $Res Function(ExtractorEvent) __);
}


/// Adds pattern-matching-related methods to [ExtractorEvent].
extension ExtractorEventPatterns on ExtractorEvent {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>({TResult Function( ExtractorEvent_Progress value)?  progress,TResult Function( ExtractorEvent_Caption value)?  caption,TResult Function( ExtractorEvent_DynamicRoi value)?  dynamicRoi,TResult Function( ExtractorEvent_Finished value)?  finished,TResult Function( ExtractorEvent_Error value)?  error,required TResult orElse(),}){
final _that = this;
switch (_that) {
case ExtractorEvent_Progress() when progress != null:
return progress(_that);case ExtractorEvent_Caption() when caption != null:
return caption(_that);case ExtractorEvent_DynamicRoi() when dynamicRoi != null:
return dynamicRoi(_that);case ExtractorEvent_Finished() when finished != null:
return finished(_that);case ExtractorEvent_Error() when error != null:
return error(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>({required TResult Function( ExtractorEvent_Progress value)  progress,required TResult Function( ExtractorEvent_Caption value)  caption,required TResult Function( ExtractorEvent_DynamicRoi value)  dynamicRoi,required TResult Function( ExtractorEvent_Finished value)  finished,required TResult Function( ExtractorEvent_Error value)  error,}){
final _that = this;
switch (_that) {
case ExtractorEvent_Progress():
return progress(_that);case ExtractorEvent_Caption():
return caption(_that);case ExtractorEvent_DynamicRoi():
return dynamicRoi(_that);case ExtractorEvent_Finished():
return finished(_that);case ExtractorEvent_Error():
return error(_that);}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>({TResult? Function( ExtractorEvent_Progress value)?  progress,TResult? Function( ExtractorEvent_Caption value)?  caption,TResult? Function( ExtractorEvent_DynamicRoi value)?  dynamicRoi,TResult? Function( ExtractorEvent_Finished value)?  finished,TResult? Function( ExtractorEvent_Error value)?  error,}){
final _that = this;
switch (_that) {
case ExtractorEvent_Progress() when progress != null:
return progress(_that);case ExtractorEvent_Caption() when caption != null:
return caption(_that);case ExtractorEvent_DynamicRoi() when dynamicRoi != null:
return dynamicRoi(_that);case ExtractorEvent_Finished() when finished != null:
return finished(_that);case ExtractorEvent_Error() when error != null:
return error(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>({TResult Function( double field0,  BigInt field1)?  progress,TResult Function( CaptionResult field0)?  caption,TResult Function( Roi field0)?  dynamicRoi,TResult Function()?  finished,TResult Function( String field0)?  error,required TResult orElse(),}) {final _that = this;
switch (_that) {
case ExtractorEvent_Progress() when progress != null:
return progress(_that.field0,_that.field1);case ExtractorEvent_Caption() when caption != null:
return caption(_that.field0);case ExtractorEvent_DynamicRoi() when dynamicRoi != null:
return dynamicRoi(_that.field0);case ExtractorEvent_Finished() when finished != null:
return finished();case ExtractorEvent_Error() when error != null:
return error(_that.field0);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>({required TResult Function( double field0,  BigInt field1)  progress,required TResult Function( CaptionResult field0)  caption,required TResult Function( Roi field0)  dynamicRoi,required TResult Function()  finished,required TResult Function( String field0)  error,}) {final _that = this;
switch (_that) {
case ExtractorEvent_Progress():
return progress(_that.field0,_that.field1);case ExtractorEvent_Caption():
return caption(_that.field0);case ExtractorEvent_DynamicRoi():
return dynamicRoi(_that.field0);case ExtractorEvent_Finished():
return finished();case ExtractorEvent_Error():
return error(_that.field0);}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>({TResult? Function( double field0,  BigInt field1)?  progress,TResult? Function( CaptionResult field0)?  caption,TResult? Function( Roi field0)?  dynamicRoi,TResult? Function()?  finished,TResult? Function( String field0)?  error,}) {final _that = this;
switch (_that) {
case ExtractorEvent_Progress() when progress != null:
return progress(_that.field0,_that.field1);case ExtractorEvent_Caption() when caption != null:
return caption(_that.field0);case ExtractorEvent_DynamicRoi() when dynamicRoi != null:
return dynamicRoi(_that.field0);case ExtractorEvent_Finished() when finished != null:
return finished();case ExtractorEvent_Error() when error != null:
return error(_that.field0);case _:
  return null;

}
}

}

/// @nodoc


class ExtractorEvent_Progress extends ExtractorEvent {
  const ExtractorEvent_Progress(this.field0, this.field1): super._();
  

 final  double field0;
 final  BigInt field1;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ExtractorEvent_ProgressCopyWith<ExtractorEvent_Progress> get copyWith => _$ExtractorEvent_ProgressCopyWithImpl<ExtractorEvent_Progress>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent_Progress&&(identical(other.field0, field0) || other.field0 == field0)&&(identical(other.field1, field1) || other.field1 == field1));
}


@override
int get hashCode => Object.hash(runtimeType,field0,field1);

@override
String toString() {
  return 'ExtractorEvent.progress(field0: $field0, field1: $field1)';
}


}

/// @nodoc
abstract mixin class $ExtractorEvent_ProgressCopyWith<$Res> implements $ExtractorEventCopyWith<$Res> {
  factory $ExtractorEvent_ProgressCopyWith(ExtractorEvent_Progress value, $Res Function(ExtractorEvent_Progress) _then) = _$ExtractorEvent_ProgressCopyWithImpl;
@useResult
$Res call({
 double field0, BigInt field1
});




}
/// @nodoc
class _$ExtractorEvent_ProgressCopyWithImpl<$Res>
    implements $ExtractorEvent_ProgressCopyWith<$Res> {
  _$ExtractorEvent_ProgressCopyWithImpl(this._self, this._then);

  final ExtractorEvent_Progress _self;
  final $Res Function(ExtractorEvent_Progress) _then;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,Object? field1 = null,}) {
  return _then(ExtractorEvent_Progress(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as double,null == field1 ? _self.field1 : field1 // ignore: cast_nullable_to_non_nullable
as BigInt,
  ));
}


}

/// @nodoc


class ExtractorEvent_Caption extends ExtractorEvent {
  const ExtractorEvent_Caption(this.field0): super._();
  

 final  CaptionResult field0;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ExtractorEvent_CaptionCopyWith<ExtractorEvent_Caption> get copyWith => _$ExtractorEvent_CaptionCopyWithImpl<ExtractorEvent_Caption>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent_Caption&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'ExtractorEvent.caption(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $ExtractorEvent_CaptionCopyWith<$Res> implements $ExtractorEventCopyWith<$Res> {
  factory $ExtractorEvent_CaptionCopyWith(ExtractorEvent_Caption value, $Res Function(ExtractorEvent_Caption) _then) = _$ExtractorEvent_CaptionCopyWithImpl;
@useResult
$Res call({
 CaptionResult field0
});




}
/// @nodoc
class _$ExtractorEvent_CaptionCopyWithImpl<$Res>
    implements $ExtractorEvent_CaptionCopyWith<$Res> {
  _$ExtractorEvent_CaptionCopyWithImpl(this._self, this._then);

  final ExtractorEvent_Caption _self;
  final $Res Function(ExtractorEvent_Caption) _then;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(ExtractorEvent_Caption(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as CaptionResult,
  ));
}


}

/// @nodoc


class ExtractorEvent_DynamicRoi extends ExtractorEvent {
  const ExtractorEvent_DynamicRoi(this.field0): super._();
  

 final  Roi field0;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ExtractorEvent_DynamicRoiCopyWith<ExtractorEvent_DynamicRoi> get copyWith => _$ExtractorEvent_DynamicRoiCopyWithImpl<ExtractorEvent_DynamicRoi>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent_DynamicRoi&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'ExtractorEvent.dynamicRoi(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $ExtractorEvent_DynamicRoiCopyWith<$Res> implements $ExtractorEventCopyWith<$Res> {
  factory $ExtractorEvent_DynamicRoiCopyWith(ExtractorEvent_DynamicRoi value, $Res Function(ExtractorEvent_DynamicRoi) _then) = _$ExtractorEvent_DynamicRoiCopyWithImpl;
@useResult
$Res call({
 Roi field0
});




}
/// @nodoc
class _$ExtractorEvent_DynamicRoiCopyWithImpl<$Res>
    implements $ExtractorEvent_DynamicRoiCopyWith<$Res> {
  _$ExtractorEvent_DynamicRoiCopyWithImpl(this._self, this._then);

  final ExtractorEvent_DynamicRoi _self;
  final $Res Function(ExtractorEvent_DynamicRoi) _then;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(ExtractorEvent_DynamicRoi(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as Roi,
  ));
}


}

/// @nodoc


class ExtractorEvent_Finished extends ExtractorEvent {
  const ExtractorEvent_Finished(): super._();
  






@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent_Finished);
}


@override
int get hashCode => runtimeType.hashCode;

@override
String toString() {
  return 'ExtractorEvent.finished()';
}


}




/// @nodoc


class ExtractorEvent_Error extends ExtractorEvent {
  const ExtractorEvent_Error(this.field0): super._();
  

 final  String field0;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ExtractorEvent_ErrorCopyWith<ExtractorEvent_Error> get copyWith => _$ExtractorEvent_ErrorCopyWithImpl<ExtractorEvent_Error>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ExtractorEvent_Error&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'ExtractorEvent.error(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $ExtractorEvent_ErrorCopyWith<$Res> implements $ExtractorEventCopyWith<$Res> {
  factory $ExtractorEvent_ErrorCopyWith(ExtractorEvent_Error value, $Res Function(ExtractorEvent_Error) _then) = _$ExtractorEvent_ErrorCopyWithImpl;
@useResult
$Res call({
 String field0
});




}
/// @nodoc
class _$ExtractorEvent_ErrorCopyWithImpl<$Res>
    implements $ExtractorEvent_ErrorCopyWith<$Res> {
  _$ExtractorEvent_ErrorCopyWithImpl(this._self, this._then);

  final ExtractorEvent_Error _self;
  final $Res Function(ExtractorEvent_Error) _then;

/// Create a copy of ExtractorEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(ExtractorEvent_Error(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as String,
  ));
}


}

/// @nodoc
mixin _$PlayerEvent {

 Object get field0;



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PlayerEvent&&const DeepCollectionEquality().equals(other.field0, field0));
}


@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(field0));

@override
String toString() {
  return 'PlayerEvent(field0: $field0)';
}


}

/// @nodoc
class $PlayerEventCopyWith<$Res>  {
$PlayerEventCopyWith(PlayerEvent _, $Res Function(PlayerEvent) __);
}


/// Adds pattern-matching-related methods to [PlayerEvent].
extension PlayerEventPatterns on PlayerEvent {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>({TResult Function( PlayerEvent_Video value)?  video,TResult Function( PlayerEvent_Caption value)?  caption,TResult Function( PlayerEvent_AutoRoiUpdated value)?  autoRoiUpdated,required TResult orElse(),}){
final _that = this;
switch (_that) {
case PlayerEvent_Video() when video != null:
return video(_that);case PlayerEvent_Caption() when caption != null:
return caption(_that);case PlayerEvent_AutoRoiUpdated() when autoRoiUpdated != null:
return autoRoiUpdated(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>({required TResult Function( PlayerEvent_Video value)  video,required TResult Function( PlayerEvent_Caption value)  caption,required TResult Function( PlayerEvent_AutoRoiUpdated value)  autoRoiUpdated,}){
final _that = this;
switch (_that) {
case PlayerEvent_Video():
return video(_that);case PlayerEvent_Caption():
return caption(_that);case PlayerEvent_AutoRoiUpdated():
return autoRoiUpdated(_that);}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>({TResult? Function( PlayerEvent_Video value)?  video,TResult? Function( PlayerEvent_Caption value)?  caption,TResult? Function( PlayerEvent_AutoRoiUpdated value)?  autoRoiUpdated,}){
final _that = this;
switch (_that) {
case PlayerEvent_Video() when video != null:
return video(_that);case PlayerEvent_Caption() when caption != null:
return caption(_that);case PlayerEvent_AutoRoiUpdated() when autoRoiUpdated != null:
return autoRoiUpdated(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>({TResult Function( VideoFrame field0)?  video,TResult Function( CaptionResult field0)?  caption,TResult Function( Roi field0)?  autoRoiUpdated,required TResult orElse(),}) {final _that = this;
switch (_that) {
case PlayerEvent_Video() when video != null:
return video(_that.field0);case PlayerEvent_Caption() when caption != null:
return caption(_that.field0);case PlayerEvent_AutoRoiUpdated() when autoRoiUpdated != null:
return autoRoiUpdated(_that.field0);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>({required TResult Function( VideoFrame field0)  video,required TResult Function( CaptionResult field0)  caption,required TResult Function( Roi field0)  autoRoiUpdated,}) {final _that = this;
switch (_that) {
case PlayerEvent_Video():
return video(_that.field0);case PlayerEvent_Caption():
return caption(_that.field0);case PlayerEvent_AutoRoiUpdated():
return autoRoiUpdated(_that.field0);}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>({TResult? Function( VideoFrame field0)?  video,TResult? Function( CaptionResult field0)?  caption,TResult? Function( Roi field0)?  autoRoiUpdated,}) {final _that = this;
switch (_that) {
case PlayerEvent_Video() when video != null:
return video(_that.field0);case PlayerEvent_Caption() when caption != null:
return caption(_that.field0);case PlayerEvent_AutoRoiUpdated() when autoRoiUpdated != null:
return autoRoiUpdated(_that.field0);case _:
  return null;

}
}

}

/// @nodoc


class PlayerEvent_Video extends PlayerEvent {
  const PlayerEvent_Video(this.field0): super._();
  

@override final  VideoFrame field0;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PlayerEvent_VideoCopyWith<PlayerEvent_Video> get copyWith => _$PlayerEvent_VideoCopyWithImpl<PlayerEvent_Video>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PlayerEvent_Video&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'PlayerEvent.video(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $PlayerEvent_VideoCopyWith<$Res> implements $PlayerEventCopyWith<$Res> {
  factory $PlayerEvent_VideoCopyWith(PlayerEvent_Video value, $Res Function(PlayerEvent_Video) _then) = _$PlayerEvent_VideoCopyWithImpl;
@useResult
$Res call({
 VideoFrame field0
});




}
/// @nodoc
class _$PlayerEvent_VideoCopyWithImpl<$Res>
    implements $PlayerEvent_VideoCopyWith<$Res> {
  _$PlayerEvent_VideoCopyWithImpl(this._self, this._then);

  final PlayerEvent_Video _self;
  final $Res Function(PlayerEvent_Video) _then;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(PlayerEvent_Video(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as VideoFrame,
  ));
}


}

/// @nodoc


class PlayerEvent_Caption extends PlayerEvent {
  const PlayerEvent_Caption(this.field0): super._();
  

@override final  CaptionResult field0;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PlayerEvent_CaptionCopyWith<PlayerEvent_Caption> get copyWith => _$PlayerEvent_CaptionCopyWithImpl<PlayerEvent_Caption>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PlayerEvent_Caption&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'PlayerEvent.caption(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $PlayerEvent_CaptionCopyWith<$Res> implements $PlayerEventCopyWith<$Res> {
  factory $PlayerEvent_CaptionCopyWith(PlayerEvent_Caption value, $Res Function(PlayerEvent_Caption) _then) = _$PlayerEvent_CaptionCopyWithImpl;
@useResult
$Res call({
 CaptionResult field0
});




}
/// @nodoc
class _$PlayerEvent_CaptionCopyWithImpl<$Res>
    implements $PlayerEvent_CaptionCopyWith<$Res> {
  _$PlayerEvent_CaptionCopyWithImpl(this._self, this._then);

  final PlayerEvent_Caption _self;
  final $Res Function(PlayerEvent_Caption) _then;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(PlayerEvent_Caption(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as CaptionResult,
  ));
}


}

/// @nodoc


class PlayerEvent_AutoRoiUpdated extends PlayerEvent {
  const PlayerEvent_AutoRoiUpdated(this.field0): super._();
  

@override final  Roi field0;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PlayerEvent_AutoRoiUpdatedCopyWith<PlayerEvent_AutoRoiUpdated> get copyWith => _$PlayerEvent_AutoRoiUpdatedCopyWithImpl<PlayerEvent_AutoRoiUpdated>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PlayerEvent_AutoRoiUpdated&&(identical(other.field0, field0) || other.field0 == field0));
}


@override
int get hashCode => Object.hash(runtimeType,field0);

@override
String toString() {
  return 'PlayerEvent.autoRoiUpdated(field0: $field0)';
}


}

/// @nodoc
abstract mixin class $PlayerEvent_AutoRoiUpdatedCopyWith<$Res> implements $PlayerEventCopyWith<$Res> {
  factory $PlayerEvent_AutoRoiUpdatedCopyWith(PlayerEvent_AutoRoiUpdated value, $Res Function(PlayerEvent_AutoRoiUpdated) _then) = _$PlayerEvent_AutoRoiUpdatedCopyWithImpl;
@useResult
$Res call({
 Roi field0
});




}
/// @nodoc
class _$PlayerEvent_AutoRoiUpdatedCopyWithImpl<$Res>
    implements $PlayerEvent_AutoRoiUpdatedCopyWith<$Res> {
  _$PlayerEvent_AutoRoiUpdatedCopyWithImpl(this._self, this._then);

  final PlayerEvent_AutoRoiUpdated _self;
  final $Res Function(PlayerEvent_AutoRoiUpdated) _then;

/// Create a copy of PlayerEvent
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? field0 = null,}) {
  return _then(PlayerEvent_AutoRoiUpdated(
null == field0 ? _self.field0 : field0 // ignore: cast_nullable_to_non_nullable
as Roi,
  ));
}


}

// dart format on
