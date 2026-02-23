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
